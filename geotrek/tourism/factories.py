# -*- coding: utf-8 -*-

from django.contrib.gis.geos import Point
from django.utils import timezone

import factory

from geotrek.authent.factories import StructureRelatedDefaultFactory
from geotrek.common.utils.testdata import get_dummy_uploaded_image, dummy_filefield_as_sequence

from . import models
from geotrek.trekking.factories import TrekFactory
from django.conf import settings


class DataSourceFactory(factory.Factory):
    FACTORY_FOR = models.DataSource

    title = factory.Sequence(lambda n: u"DataSource %s" % n)
    url = factory.Sequence(lambda n: u"http://%s.com" % n)
    type = models.DATA_SOURCE_TYPES.GEOJSON
    pictogram = u"{}".format(get_dummy_uploaded_image())


class InformationDeskTypeFactory(factory.Factory):
    FACTORY_FOR = models.InformationDeskType

    label = factory.Sequence(lambda n: u"Type %s" % n)
    pictogram = get_dummy_uploaded_image()


class InformationDeskFactory(factory.Factory):
    FACTORY_FOR = models.InformationDesk

    name = factory.Sequence(lambda n: u"information desk name %s" % n)
    type = factory.SubFactory(InformationDeskTypeFactory)
    description = factory.Sequence(lambda n: u"<p>description %s</p>" % n)
    phone = factory.Sequence(lambda n: u"01 02 03 %s" % n)
    email = factory.Sequence(lambda n: u"email-%s@makina-corpus.com" % n)
    website = factory.Sequence(lambda n: u"http://makina-corpus.com/%s" % n)
    photo = dummy_filefield_as_sequence(u'photo %s')
    street = factory.Sequence(lambda n: u"%s baker street" % n)
    postal_code = u'28300'
    municipality = factory.Sequence(lambda n: u"Bailleau L'évêque-%s" % n)
    geom = Point(3.14, 42)


class TouristicContentCategoryFactory(factory.Factory):
    FACTORY_FOR = models.TouristicContentCategory

    label = factory.Sequence(lambda n: u"Category %s" % n)
    type1_label = factory.Sequence(lambda n: u"Type1_label %s" % n)
    # Keep type2_label with default value
    pictogram = dummy_filefield_as_sequence(u'thumbnail %s')


class TouristicContentTypeFactory(factory.Factory):
    FACTORY_FOR = models.TouristicContentType

    label = factory.Sequence(lambda n: u"Type %s" % n)
    category = factory.SubFactory(TouristicContentCategoryFactory)
    pictogram = dummy_filefield_as_sequence(u'thumbnail %s')
    in_list = 1


class ReservationSystemFactory(factory.Factory):
    FACTORY_FOR = models.ReservationSystem

    name = factory.Sequence(lambda n: u"ReservationSystem %s" % n)


class TouristicContentFactory(StructureRelatedDefaultFactory):
    FACTORY_FOR = models.TouristicContent

    name = factory.Sequence(lambda n: u"TouristicContent %s" % n)
    category = factory.SubFactory(TouristicContentCategoryFactory)
    geom = 'POINT(0 0)'
    published = True
    reservation_system = factory.SubFactory(ReservationSystemFactory)
    reservation_id = u'XXXXXXXXX'


class TouristicEventTypeFactory(factory.Factory):
    FACTORY_FOR = models.TouristicEventType

    type = factory.Sequence(lambda n: u"Type %s" % n)
    pictogram = dummy_filefield_as_sequence(u'thumbnail %s')


class TouristicEventFactory(factory.Factory):
    FACTORY_FOR = models.TouristicEvent

    name = factory.Sequence(lambda n: u"TouristicEvent %s" % n)
    geom = 'POINT(0 0)'
    published = True
    begin_date = timezone.now()
    end_date = timezone.now()

    type = factory.SubFactory(TouristicEventTypeFactory)


class TrekWithTouristicEventFactory(TrekFactory):
    @classmethod
    def _prepare(cls, create, **kwargs):
        trek = super(TrekWithTouristicEventFactory, cls)._prepare(create, **kwargs)
        TouristicEventFactory.create(geom='POINT(700000 6600000)')
        TouristicEventFactory.create(geom='POINT(700100 6600100)')

        if create:
            for lang in settings.MODELTRANSLATION_LANGUAGES:
                setattr(trek, u'published_{}'.format(lang), True)
            trek.save()

        return trek


class TrekWithTouristicContentFactory(TrekFactory):
    @classmethod
    def _prepare(cls, create, **kwargs):
        trek = super(TrekWithTouristicContentFactory, cls)._prepare(create, **kwargs)
        TouristicContentFactory.create(category=TouristicContentCategoryFactory(label=u"Restaurant"),
                                       geom='POINT(700000 6600000)')
        TouristicContentFactory.create(category=TouristicContentCategoryFactory(label=u"Musée"),
                                       geom='POINT(700100 6600100)')

        if create:
            for lang in settings.MODELTRANSLATION_LANGUAGES:
                setattr(trek, u'published_{}'.format(lang), True)
            trek.save()

        return trek
