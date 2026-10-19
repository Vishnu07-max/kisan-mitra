from rest_framework import generics
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.farms.models import Farm

from .inference import FEATURES, ModelNotAvailable, recommend
from .models import Recommendation
from .serializers import RecommendationSerializer, RecommendInputSerializer


class ModelUnavailable(APIException):
    status_code = 503
    default_detail = "The crop recommendation model is not available right now."
    default_code = "model_unavailable"


class HistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class RecommendView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "crops"

    def post(self, request):
        ser = RecommendInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        farm = None
        if data.get("farm_id") is not None:
            farm = Farm.objects.filter(pk=data["farm_id"], owner=request.user).first()
            if farm is None:
                raise ValidationError({"farm_id": ["Unknown farm."]})

        values = {f: float(data[f]) for f in FEATURES if data.get(f) is not None}
        try:
            result = recommend(values)
        except ModelNotAvailable:
            raise ModelUnavailable()

        rec = Recommendation.objects.create(
            owner=request.user, farm=farm, inputs=values, input_set=result["input_set"],
            suggestions=result["suggestions"], warnings=result["warnings"],
            model_version=result["model_version"],
        )
        out = dict(RecommendationSerializer(rec).data)
        for key in ("cv_accuracy", "chance_level", "crops_covered", "not_covered"):
            out[key] = result[key]
        return Response(out, status=201)


class RecommendationListView(generics.ListAPIView):
    serializer_class = RecommendationSerializer
    pagination_class = HistoryPagination

    def get_queryset(self):
        return Recommendation.objects.filter(owner=self.request.user)


class RecommendationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        return Recommendation.objects.filter(owner=self.request.user)