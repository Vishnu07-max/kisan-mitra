from django.conf import settings
from django.db import models


class Recommendation(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations")
    farm = models.ForeignKey("farms.Farm", on_delete=models.SET_NULL, null=True, blank=True, related_name="recommendations")
    inputs = models.JSONField()
    input_set = models.CharField(max_length=40)
    suggestions = models.JSONField()
    warnings = models.JSONField(default=list, blank=True)
    model_version = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return f"{self.owner_id}: {self.input_set}"