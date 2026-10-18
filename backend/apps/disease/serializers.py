from django.urls import reverse
from rest_framework import serializers

from .models import DiseaseAssessment


class AssessmentSerializer(serializers.ModelSerializer):
    farm_id = serializers.IntegerField(read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = DiseaseAssessment
        fields = [
            "id", "status", "reason", "outcome", "experimental", "crop", "condition",
            "is_healthy", "confidence", "top_k", "model_version", "inference_ms",
            "farm_id", "image_url", "created_at",
        ]
        read_only_fields = fields

    def get_image_url(self, obj):
        return reverse("assessment-image", args=[obj.pk])