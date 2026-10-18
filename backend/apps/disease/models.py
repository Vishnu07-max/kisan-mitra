from django.conf import settings
from django.db import models


class DiseaseAssessment(models.Model):
    """One Crop Doctor result. A 'no_match' row stores NO disease label."""

    class Status(models.TextChoices):
        OK = "ok", "Result"
        NO_MATCH = "no_match", "No match found"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessments"
    )
    farm = models.ForeignKey(
        "farms.Farm", on_delete=models.SET_NULL, null=True, blank=True, related_name="assessments"
    )
    image = models.FileField(upload_to="assessments/%Y/%m/")
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=30, blank=True)
    outcome = models.CharField(max_length=30, blank=True)
    experimental = models.BooleanField(default=False)
    label = models.CharField(max_length=120, blank=True)
    crop = models.CharField(max_length=60, blank=True)
    condition = models.CharField(max_length=80, blank=True)
    is_healthy = models.BooleanField(default=False)
    confidence = models.FloatField()
    top_k = models.JSONField(default=list, blank=True)
    model_version = models.CharField(max_length=30)
    inference_ms = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return f"{self.owner_id}: {self.status} {self.label or '-'}"