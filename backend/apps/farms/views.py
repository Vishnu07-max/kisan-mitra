from django.shortcuts import get_object_or_404
from rest_framework import generics, viewsets

from .models import CropRecord, Farm
from .serializers import CropRecordSerializer, FarmSerializer


class FarmViewSet(viewsets.ModelViewSet):
    """Farmers only ever see and change their OWN farms."""

    serializer_class = FarmSerializer

    def get_queryset(self):
        return Farm.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


def get_owned_farm(request, farm_id):
    # 404 (not 403) so we don't even reveal that another farmer's farm exists
    return get_object_or_404(Farm, pk=farm_id, owner=request.user)


class FarmCropListCreateView(generics.ListCreateAPIView):
    serializer_class = CropRecordSerializer

    def get_queryset(self):
        farm = get_owned_farm(self.request, self.kwargs["farm_id"])
        return farm.crop_records.all()

    def perform_create(self, serializer):
        serializer.save(farm=get_owned_farm(self.request, self.kwargs["farm_id"]))


class FarmCropDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CropRecordSerializer

    def get_queryset(self):
        return CropRecord.objects.filter(
            farm_id=self.kwargs["farm_id"], farm__owner=self.request.user
        )