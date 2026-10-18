from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.farms.models import Farm

from .images import read_and_prepare
from .inference import InvalidImage, ModelNotAvailable, predict
from .models import DiseaseAssessment
from .serializers import AssessmentSerializer


class ModelUnavailable(APIException):
    status_code = 503
    default_detail = "The Crop Doctor model is not available right now."
    default_code = "model_unavailable"


class HistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class PredictView(APIView):
    parser_classes = [MultiPartParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "disease"

    def post(self, request):
        upload = request.FILES.get("image")
        if upload is None:
            raise ValidationError({"image": ["This field is required."]})

        farm = None
        farm_id = request.data.get("farm_id")
        if farm_id not in (None, ""):
            try:
                farm = Farm.objects.get(pk=int(farm_id), owner=request.user)
            except (ValueError, Farm.DoesNotExist):
                raise ValidationError({"farm_id": ["Unknown farm."]})

        max_bytes = int(settings.DISEASE_MAX_UPLOAD_MB * 1024 * 1024)
        raw, stored = read_and_prepare(upload, max_bytes)
        try:
            result = predict(raw)
        except InvalidImage as exc:
            raise ValidationError({"image": [str(exc)]})
        except ModelNotAvailable:
            raise ModelUnavailable()

        top = result.get("top_prediction") or {}
        assessment = DiseaseAssessment(
            owner=request.user,
            farm=farm,
            status=result["status"],
            reason=result.get("reason") or "",
            outcome=result.get("outcome", ""),
            experimental=result.get("experimental", False),
            label=top.get("label", ""),
            crop=top.get("crop", ""),
            condition=top.get("condition", ""),
            is_healthy=top.get("is_healthy", False),
            confidence=result["max_confidence"],
            top_k=result.get("top_k", []),
            model_version=result["model_version"],
            inference_ms=result.get("inference_ms"),
        )
        assessment.image.save(f"{uuid4().hex}.jpg", ContentFile(stored), save=False)
        assessment.save()

        data = dict(AssessmentSerializer(assessment).data)
        data["supported_crops"] = result.get("supported_crops", [])
        data["experimental_crops"] = result.get("experimental_crops", [])
        return Response(data, status=201)


class AssessmentListView(generics.ListAPIView):
    serializer_class = AssessmentSerializer
    pagination_class = HistoryPagination

    def get_queryset(self):
        return DiseaseAssessment.objects.filter(owner=self.request.user)


class AssessmentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        return DiseaseAssessment.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        instance.image.delete(save=False)
        instance.delete()


class AssessmentImageView(APIView):
    """Only the owner can fetch the photo. 404 (not 403) for anyone else."""

    def get(self, request, pk):
        assessment = get_object_or_404(DiseaseAssessment, pk=pk, owner=request.user)
        try:
            handle = assessment.image.open("rb")
        except FileNotFoundError:
            raise NotFound("The image file is no longer available.")
        response = FileResponse(handle, content_type="image/jpeg")
        response["Cache-Control"] = "private, max-age=3600"
        response["X-Content-Type-Options"] = "nosniff"
        return response