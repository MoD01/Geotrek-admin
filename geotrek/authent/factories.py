import factory

from django.conf import settings
from django.contrib.auth.models import Group

from mapentity.factories import UserFactory
from . import models as core_models


class PathManagerFactory(UserFactory):
    is_staff = True

    @classmethod
    def _prepare(cls, create, **kwargs):
        GROUP_PATH_MANAGER_ID = settings.AUTHENT_GROUPS_MAPPING['PATH_MANAGER']
        pathmanager = Group.objects.get(pk=GROUP_PATH_MANAGER_ID)
        kwargs.setdefault('groups', []).append(pathmanager)
        return super(PathManagerFactory, cls)._prepare(create, **kwargs)


class TrekkingManagerFactory(UserFactory):
    is_staff = True

    @classmethod
    def _prepare(cls, create, **kwargs):
        GROUP_TREKKING_MANAGER_ID = settings.AUTHENT_GROUPS_MAPPING['TREKKING_MANAGER']
        pathmanager = Group.objects.get(pk=GROUP_TREKKING_MANAGER_ID)
        kwargs.setdefault('groups', []).append(pathmanager)
        return super(TrekkingManagerFactory, cls)._prepare(create, **kwargs)


class StructureFactory(factory.Factory):
    FACTORY_FOR = core_models.Structure

    name = factory.Sequence('structure {0}'.format)


# Abstract
class StructureRelatedRandomFactory(factory.Factory):
    """Create a new structure each time"""
    FACTORY_FOR = core_models.StructureRelated

    # Return the default structure
    structure = factory.SubFactory(StructureFactory)


# Abstract
class StructureRelatedDefaultFactory(factory.Factory):
    """Use the default structure"""
    FACTORY_FOR = core_models.StructureRelated

    structure = factory.LazyAttribute(lambda _: core_models.default_structure_instance())


class UserProfileFactory(StructureRelatedDefaultFactory):
    """
    Create a normal user (language=fr and structure=default)
    """
    FACTORY_FOR = core_models.UserProfile

    user = factory.SubFactory(UserFactory)
    language = 'fr'
