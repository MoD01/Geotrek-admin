from rest_framework import permissions as rest_permissions
from rest_framework import viewsets

from django.core.urlresolvers import reverse_lazy
from django.views.generic import CreateView, UpdateView

from geotrek.flatpages.serializers import FlatPageSerializer
from geotrek.flatpages import models as flatpages_models

from .forms import FlatPageForm


class FlatPageViewSet(viewsets.ModelViewSet):
    """
    A viewset for viewing and editing flat pages instances.
    """
    serializer_class = FlatPageSerializer
    permission_classes = [rest_permissions.DjangoModelPermissionsOrAnonReadOnly]
    queryset = flatpages_models.FlatPage.objects.filter(published=True)

    def get_queryset(self):
        qs = flatpages_models.FlatPage.objects.filter(published=True)
        if 'source' in self.request.GET:
            qs = qs.filter(source__name__in=self.request.GET['source'].split(','))
        return qs


class FlatPageEditMixin(object):
    model = flatpages_models.FlatPage
    form_class = FlatPageForm
    success_url = reverse_lazy('admin:flatpages_flatpage_changelist')

    def get_form_kwargs(self):
        kwargs = super(FlatPageEditMixin, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class FlatPageCreate(FlatPageEditMixin, CreateView):
    pass


class FlatPageUpdate(FlatPageEditMixin, UpdateView):
    pass
