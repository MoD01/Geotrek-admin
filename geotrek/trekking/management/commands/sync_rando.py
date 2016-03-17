# -*- encoding: UTF-8 -

import logging
from optparse import make_option
import os
import re
import sys
import shutil
from time import sleep
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.test.client import RequestFactory
from django.utils import translation
from django.utils.translation import ugettext as _
from landez import TilesManager
from landez.sources import DownloadError
from geotrek.altimetry.views import ElevationProfile, ElevationArea, serve_elevation_chart
from geotrek.common import models as common_models
from geotrek.common.views import ThemeViewSet
from geotrek.core.views import ParametersView
from geotrek.feedback.views import CategoryList as FeedbackCategoryList
from geotrek.flatpages.views import FlatPageViewSet
from geotrek.tourism import models as tourism_models
from geotrek.tourism.views import TrekTouristicContentAndPOIViewSet
from geotrek.trekking import models as trekking_models
from geotrek.trekking.views import (TrekViewSet, POIViewSet, TrekPOIViewSet,
                                    TrekGPXDetail, TrekKMLDetail, TrekServiceViewSet,
                                    ServiceViewSet, TrekDocumentPublic)

# Register mapentity models
from geotrek.trekking import urls  # NOQA


logger = logging.getLogger(__name__)


class ZipTilesBuilder(object):
    def __init__(self, filepath, close_zip, **builder_args):
        builder_args['tile_format'] = self.format_from_url(builder_args['tiles_url'])
        self.close_zip = close_zip
        self.zipfile = ZipFile(filepath, 'w')
        self.tm = TilesManager(**builder_args)
        self.tiles = set()

    def format_from_url(self, url):
        """
        Try to guess the tile mime type from the tiles URL.
        Should work with basic stuff like `http://osm.org/{z}/{x}/{y}.png`
        or funky stuff like WMTS (`http://server/wmts?LAYER=...FORMAT=image/jpeg...)
        """
        m = re.search(r'FORMAT=([a-zA-Z/]+)&', url)
        if m:
            return m.group(1)
        return url.rsplit('.')[-1]

    def add_coverage(self, bbox, zoomlevels):
        self.tiles |= set(self.tm.tileslist(bbox, zoomlevels))

    def run(self):
        for tile in self.tiles:
            name = '{0}/{1}/{2}.png'.format(*tile)
            try:
                data = self.tm.tile(tile)
            except DownloadError:
                logger.warning("Failed to download tile %s" % name)
            else:
                self.zipfile.writestr(name, data)
        self.close_zip(self.zipfile)


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--url', '-u', action='store', dest='url',
                    default='http://localhost', help='Base url'),
        make_option('--source', '-s', action='store', dest='source',
                    default=None, help='Filter by source(s)'),
        make_option('--skip-pdf', '-p', action='store_true', dest='skip_pdf',
                    default=False, help='Skip generation of PDF files'),
        make_option('--skip-tiles', '-t', action='store_true', dest='skip_tiles',
                    default=False, help='Skip generation of zip tiles files'),
        make_option('--skip-dem', '-d', action='store_true', dest='skip_dem',
                    default=False, help='Skip generation of DEM files for 3D'),
        make_option('--skip-profile-png', '-e', action='store_true', dest='skip_profile_png',
                    default=False, help='Skip generation of PNG elevation profile'),
        make_option('--languages', '-l', action='store', dest='languages',
                    default='', help='Languages to sync'),
    )

    def mkdirs(self, name):
        dirname = os.path.dirname(name)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    def sync_global_tiles(self):
        """ Creates a tiles file on the global extent.
        """
        zipname = os.path.join('zip', 'tiles', 'global.zip')

        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m**\x1b[0m \x1b[1m{name}\x1b[0m ...".format(name=zipname), ending="")
            self.stdout.flush()

        global_extent = settings.LEAFLET_CONFIG['SPATIAL_EXTENT']

        logger.info("Global extent is %s" % unicode(global_extent))
        global_file = os.path.join(self.tmp_root, zipname)

        logger.info("Build global tiles file...")
        self.mkdirs(global_file)

        def close_zip(zipfile):
            return self.close_zip(zipfile, zipname)

        tiles = ZipTilesBuilder(global_file, close_zip, **self.builder_args)
        tiles.add_coverage(bbox=global_extent,
                           zoomlevels=settings.MOBILE_TILES_GLOBAL_ZOOMS)
        tiles.run()

    def sync_trek_tiles(self, trek):
        """ Creates a tiles file for the specified Trek object.
        """
        zipname = os.path.join('zip', 'tiles', '{pk}.zip'.format(pk=trek.pk))

        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m**\x1b[0m \x1b[1m{name}\x1b[0m ...".format(name=zipname), ending="")
            self.stdout.flush()

        trek_file = os.path.join(self.tmp_root, zipname)

        def _radius2bbox(lng, lat, radius):
            return (lng - radius, lat - radius,
                    lng + radius, lat + radius)

        self.mkdirs(trek_file)

        def close_zip(zipfile):
            return self.close_zip(zipfile, zipname)

        tiles = ZipTilesBuilder(trek_file, close_zip, **self.builder_args)

        geom = trek.geom
        if geom.geom_type == 'MultiLineString':
            geom = geom[0]  # FIXME
        geom.transform(4326)

        for (lng, lat) in geom.coords:
            large = _radius2bbox(lng, lat, settings.MOBILE_TILES_RADIUS_LARGE)
            small = _radius2bbox(lng, lat, settings.MOBILE_TILES_RADIUS_SMALL)
            tiles.add_coverage(bbox=large, zoomlevels=settings.MOBILE_TILES_LOW_ZOOMS)
            tiles.add_coverage(bbox=small, zoomlevels=settings.MOBILE_TILES_HIGH_ZOOMS)

        tiles.run()

    def sync_view(self, lang, view, name, url='/', params={}, zipfile=None, **kwargs):
        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m{lang}\x1b[0m \x1b[1m{name}\x1b[0m ...".format(lang=lang, name=name), ending="")
            self.stdout.flush()
        fullname = os.path.join(self.tmp_root, name)
        self.mkdirs(fullname)
        request = self.factory.get(url, params, HTTP_HOST=self.host)
        request.LANGUAGE_CODE = lang
        request.user = AnonymousUser()
        try:
            response = view(request, **kwargs)
        except Exception as e:
            self.successfull = False
            if self.verbosity == '2':
                self.stdout.write(u"\x1b[3D\x1b[31mfailed ({})\x1b[0m".format(e))
            return
        if hasattr(response, 'render'):
            response.render()
        if response.status_code != 200:
            self.successfull = False
            if self.verbosity == '2':
                self.stdout.write(u"\x1b[3D\x1b[31;1mfailed (HTTP {code})\x1b[0m".format(code=response.status_code))
            return
        f = open(fullname, 'w')
        if getattr(response, 'content', None):
            f.write(response.content)
        elif getattr(response, 'streaming_content', None):
            f.write(str(response.streaming_content))
        f.close()
        if zipfile:
            zipfile.write(fullname, name)
        if self.verbosity == '2':
            self.stdout.write(u"\x1b[3D\x1b[32mgenerated\x1b[0m")

    def sync_json(self, lang, viewset, name, zipfile=None, params={}, as_view_args=[], **kwargs):
        view = viewset.as_view(*as_view_args)
        name = os.path.join('api', lang, '{name}.json'.format(name=name))
        if self.source:
            params['source'] = ','.join(self.source)
        self.sync_view(lang, view, name, params=params, zipfile=zipfile, **kwargs)

    def sync_geojson(self, lang, viewset, name, zipfile=None, params={}, **kwargs):
        view = viewset.as_view({'get': 'list'})
        name = os.path.join('api', lang, name)
        params.update({'format': 'geojson'})
        if self.source:
            params['source'] = ','.join(self.source)
        self.sync_view(lang, view, name, params=params, zipfile=zipfile, **kwargs)

    def sync_trek_pois(self, lang, trek, zipfile=None):
        params = {'format': 'geojson'}
        if settings.ZIP_TOURISTIC_CONTENTS_AS_POI:
            view = TrekTouristicContentAndPOIViewSet.as_view({'get': 'list'})
            name = os.path.join('api', lang, 'treks', str(trek.pk), 'pois.geojson')
            self.sync_view(lang, view, name, params=params, zipfile=zipfile, pk=trek.pk)
            view = TrekPOIViewSet.as_view({'get': 'list'})
            self.sync_view(lang, view, name, params=params, zipfile=None, pk=trek.pk)
        else:
            view = TrekPOIViewSet.as_view({'get': 'list'})
            name = os.path.join('api', lang, 'treks', str(trek.pk), 'pois.geojson')
            self.sync_view(lang, view, name, params=params, zipfile=zipfile, pk=trek.pk)

    def sync_trek_services(self, lang, trek, zipfile=None):
        view = TrekServiceViewSet.as_view({'get': 'list'})
        name = os.path.join('api', lang, 'treks', str(trek.pk), 'services.geojson')
        self.sync_view(lang, view, name, params={'format': 'geojson'}, zipfile=zipfile, pk=trek.pk)

    def sync_object_view(self, lang, obj, view, basename_fmt, zipfile=None, **kwargs):
        modelname = obj._meta.model_name
        name = os.path.join('api', lang, '{modelname}s'.format(modelname=modelname), str(obj.pk), basename_fmt.format(obj=obj))
        self.sync_view(lang, view, name, zipfile=zipfile, pk=obj.pk, **kwargs)

    def sync_trek_pdf(self, lang, obj):
        if self.skip_pdf:
            return
        view = TrekDocumentPublic.as_view(model=type(obj))
        self.sync_object_view(lang, obj, view, '{obj.slug}.pdf')

    def sync_profile_json(self, lang, obj, zipfile=None):
        view = ElevationProfile.as_view(model=type(obj))
        self.sync_object_view(lang, obj, view, 'profile.json', zipfile=zipfile)

    def sync_profile_png(self, lang, obj, zipfile=None):
        view = serve_elevation_chart
        model_name = type(obj)._meta.model_name
        self.sync_object_view(lang, obj, view, 'profile.png', zipfile=zipfile, model_name=model_name, from_command=True)

    def sync_dem(self, lang, obj):
        if self.skip_dem:
            return
        view = ElevationArea.as_view(model=type(obj))
        self.sync_object_view(lang, obj, view, 'dem.json')

    def sync_gpx(self, lang, obj):
        self.sync_object_view(lang, obj, TrekGPXDetail.as_view(), '{obj.slug}.gpx')

    def sync_kml(self, lang, obj):
        self.sync_object_view(lang, obj, TrekKMLDetail.as_view(), '{obj.slug}.kml')

    def sync_file(self, lang, name, src_root, url, zipfile=None):
        url = url.strip('/')
        src = os.path.join(src_root, name)
        dst = os.path.join(self.tmp_root, url, name)
        self.mkdirs(dst)
        shutil.copyfile(src, dst)
        if zipfile:
            zipfile.write(dst, os.path.join(url, name))
        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m{lang}\x1b[0m \x1b[1m{url}/{name}\x1b[0m \x1b[32mcopied\x1b[0m".format(lang=lang, url=url, name=name))

    def sync_static_file(self, lang, name):
        self.sync_file(lang, name, settings.STATIC_ROOT, settings.STATIC_URL)

    def sync_media_file(self, lang, field, zipfile=None):
        if field and field.name:
            self.sync_file(lang, field.name, settings.MEDIA_ROOT, settings.MEDIA_URL, zipfile=zipfile)

    def sync_pictograms(self, lang, model, zipfile=None):
        for obj in model.objects.all():
            self.sync_media_file(lang, obj.pictogram, zipfile=zipfile)

    def sync_poi_media(self, lang, poi):
        if poi.resized_pictures:
            self.sync_media_file(lang, poi.resized_pictures[0][1], zipfile=self.trek_zipfile)
        for picture, resized in poi.resized_pictures[1:]:
            self.sync_media_file(lang, resized)

    def sync_trek(self, lang, trek):
        zipname = os.path.join('zip', 'treks', lang, '{pk}.zip'.format(pk=trek.pk))
        zipfullname = os.path.join(self.tmp_root, zipname)
        self.mkdirs(zipfullname)
        self.trek_zipfile = ZipFile(zipfullname, 'w')

        self.sync_json(lang, ParametersView, 'parameters', zipfile=self.zipfile)
        self.sync_json(lang, ThemeViewSet, 'themes', as_view_args=[{'get': 'list'}], zipfile=self.zipfile)
        self.sync_trek_pois(lang, trek, zipfile=self.zipfile)
        self.sync_trek_services(lang, trek, zipfile=self.zipfile)
        self.sync_gpx(lang, trek)
        self.sync_kml(lang, trek)
        self.sync_trek_pdf(lang, trek)
        self.sync_profile_json(lang, trek)
        if not self.skip_profile_png:
            self.sync_profile_png(lang, trek, zipfile=self.zipfile)
        self.sync_dem(lang, trek)
        for desk in trek.information_desks.all():
            self.sync_media_file(lang, desk.thumbnail, zipfile=self.trek_zipfile)
        for poi in trek.published_pois:
            self.sync_poi_media(lang, poi)
        if settings.ZIP_TOURISTIC_CONTENTS_AS_POI:
            for content in trek.published_touristic_contents:
                if content.resized_pictures:
                    self.sync_media_file(lang, content.resized_pictures[0][1], zipfile=self.trek_zipfile)
        self.sync_media_file(lang, trek.thumbnail, zipfile=self.zipfile)
        for picture, resized in trek.resized_pictures:
            self.sync_media_file(lang, resized, zipfile=self.trek_zipfile)

        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m{lang}\x1b[0m \x1b[1m{name}\x1b[0m ...".format(lang=lang, name=zipname), ending="")

        self.close_zip(self.trek_zipfile, zipname)

    def close_zip(self, zipfile, name):
        oldzipfilename = os.path.join(self.dst_root, name)
        zipfilename = os.path.join(self.tmp_root, name)
        try:
            oldzipfile = ZipFile(oldzipfilename, 'r')
        except IOError:
            uptodate = False
        else:
            old = set([(zi.filename, zi.CRC) for zi in oldzipfile.infolist()])
            new = set([(zi.filename, zi.CRC) for zi in zipfile.infolist()])
            uptodate = (old == new)
            oldzipfile.close()

        zipfile.close()
        if uptodate:
            stat = os.stat(oldzipfilename)
            os.utime(zipfilename, (stat.st_atime, stat.st_mtime))

        if self.verbosity == '2':
            if uptodate:
                self.stdout.write(u"\x1b[3D\x1b[32munchanged\x1b[0m")
            else:
                self.stdout.write(u"\x1b[3D\x1b[32mzipped\x1b[0m")

    def sync_trekking(self, lang):
        zipname = os.path.join('zip', 'treks', lang, 'global.zip')
        zipfullname = os.path.join(self.tmp_root, zipname)
        self.mkdirs(zipfullname)
        self.zipfile = ZipFile(zipfullname, 'w')

        self.sync_geojson(lang, TrekViewSet, 'treks.geojson', zipfile=self.zipfile)
        self.sync_geojson(lang, POIViewSet, 'pois.geojson')
        self.sync_geojson(lang, FlatPageViewSet, 'flatpages.geojson', zipfile=self.zipfile)
        self.sync_geojson(lang, ServiceViewSet, 'services.geojson', zipfile=self.zipfile)
        self.sync_view(lang, FeedbackCategoryList.as_view(),
                       os.path.join('api', lang, 'feedback', 'categories.json'),
                       zipfile=self.zipfile)
        self.sync_static_file(lang, 'trekking/trek.svg')
        self.sync_pictograms(lang, common_models.Theme, zipfile=self.zipfile)
        self.sync_pictograms(lang, common_models.RecordSource, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.TrekNetwork, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.Practice, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.Accessibility, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.DifficultyLevel, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.POIType, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.ServiceType, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.Route, zipfile=self.zipfile)
        self.sync_pictograms(lang, trekking_models.WebLinkCategory)
        if settings.ZIP_TOURISTIC_CONTENTS_AS_POI:
            self.sync_pictograms('**', tourism_models.TouristicContentCategory, zipfile=self.zipfile)

        treks = trekking_models.Trek.objects.existing().order_by('pk')
        treks = treks.filter(Q(**{'published_{lang}'.format(lang=lang): True}) | Q(**{'trek_parents__parent__published_{lang}'.format(lang=lang): True}))

        if self.source:
            treks = treks.filter(source__name__in=self.source)

        for trek in treks:
            self.sync_trek(lang, trek)

        if self.verbosity == '2':
            self.stdout.write(u"\x1b[36m{lang}\x1b[0m \x1b[1m{name}\x1b[0m ...".format(lang=lang, name=zipname), ending="")

        self.close_zip(self.zipfile, zipname)

    def sync_tiles(self):
        if not self.skip_tiles:

            if self.celery_task:
                self.celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'name': self.celery_task.name,
                        'current': 10,
                        'total': 100,
                        'infos': u"{}".format(_(u"Global tiles syncing ..."))
                    }
                )

            self.sync_global_tiles()

            if self.celery_task:
                self.celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'name': self.celery_task.name,
                        'current': 20,
                        'total': 100,
                        'infos': u"{}".format(_(u"Trek tiles syncing ..."))
                    }
                )

            treks = trekking_models.Trek.objects.existing().order_by('pk')
            if self.source:
                treks = treks.filter(source__name__in=self.source)

            for trek in treks:
                if trek.any_published or any([parent.any_published for parent in trek.parents]):
                    self.sync_trek_tiles(trek)

            if self.celery_task:
                self.celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'name': self.celery_task.name,
                        'current': 30,
                        'total': 100,
                        'infos': u"{}".format(_(u"Tiles synced ..."))
                    }
                )

    def sync(self):
        self.sync_tiles()

        step_value = int(50 / len(settings.MODELTRANSLATION_LANGUAGES))
        current_value = 30

        for lang in self.languages:
            if self.celery_task:
                self.celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'name': self.celery_task.name,
                        'current': current_value + step_value,
                        'total': 100,
                        'infos': u"{} : {} ...".format(_(u"Language"), lang)
                    }
                )
                current_value = current_value + step_value

            translation.activate(lang)
            self.sync_trekking(lang)
            translation.deactivate()

    def check_dst_root_is_empty(self):
        if not os.path.exists(self.dst_root):
            return
        existing = set([os.path.basename(p) for p in os.listdir(self.dst_root)])
        remaining = existing - set(('api', 'media', 'static', 'zip'))
        if remaining:
            raise CommandError(u"Destination directory contains extra data")

    def rename_root(self):
        if os.path.exists(self.dst_root):
            tmp_root2 = os.path.join(os.path.dirname(self.dst_root), 'deprecated_sync_rando')
            os.rename(self.dst_root, tmp_root2)
            os.rename(self.tmp_root, self.dst_root)
            shutil.rmtree(tmp_root2)
        else:
            os.rename(self.tmp_root, self.dst_root)

    def handle(self, *args, **options):
        self.successfull = True
        self.verbosity = options.get('verbosity', '1')
        if len(args) < 1:
            raise CommandError(u"Missing parameter destination directory")
        self.dst_root = args[0].rstrip('/')
        self.check_dst_root_is_empty()
        if(options['url'][:7] != 'http://'):
            raise CommandError('url parameter should start with http://')
        self.referer = options['url']
        self.host = self.referer[7:]
        self.factory = RequestFactory()
        self.tmp_root = os.path.join(os.path.dirname(self.dst_root), 'tmp_sync_rando')
        os.mkdir(self.tmp_root)
        self.skip_pdf = options['skip_pdf']
        self.skip_tiles = options['skip_tiles']
        self.skip_dem = options['skip_dem']
        self.skip_profile_png = options['skip_profile_png']
        self.source = options['source']
        if options['languages']:
            self.languages = options['languages'].split(',')
        else:
            self.languages = settings.MODELTRANSLATION_LANGUAGES
        self.celery_task = options.get('task', None)

        if self.source is not None:
            self.source = self.source.split(',')
        self.builder_args = {
            'tiles_url': settings.MOBILE_TILES_URL,
            'tiles_headers': {"Referer": self.referer},
            'ignore_errors': True,
            'tiles_dir': os.path.join(settings.DEPLOY_ROOT, 'var', 'tiles'),
        }

        try:
            self.sync()
            if self.celery_task:
                self.celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'name': self.celery_task.name,
                        'current': 100,
                        'total': 100,
                        'infos': u"{}".format(_(u"Sync ended"))
                    }
                )
        except:
            shutil.rmtree(self.tmp_root)
            raise

        self.rename_root()

        if self.verbosity >= '1':
            self.stdout.write('Done')

        if not self.successfull:
            self.stdout.write('Some errors raised during synchronization.')
            sys.exit(1)

        sleep(2)  # end sleep to ensure sync page get result
