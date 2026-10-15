from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Farm(models.Model):
    """A piece of land owned by one farmer."""

    class SoilType(models.TextChoices):
        ALLUVIAL = "alluvial", "Alluvial"
        BLACK = "black", "Black (Regur)"
        RED = "red", "Red"
        LATERITE = "laterite", "Laterite"
        SANDY = "sandy", "Sandy"
        LOAMY = "loamy", "Loamy"
        CLAY = "clay", "Clay"
        UNKNOWN = "unknown", "Not sure"

    class Irrigation(models.TextChoices):
        RAINFED = "rainfed", "Rainfed"
        CANAL = "canal", "Canal"
        TUBEWELL = "tubewell", "Tubewell / Borewell"
        DRIP = "drip", "Drip"
        SPRINKLER = "sprinkler", "Sprinkler"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="farms"
    )
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=60)
    district = models.CharField(max_length=60)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    soil_type = models.CharField(
        max_length=20, choices=SoilType.choices, default=SoilType.UNKNOWN
    )
    irrigation_type = models.CharField(
        max_length=20, choices=Irrigation.choices, default=Irrigation.RAINFED
    )
    area_acres = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0.01)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_farm_name_per_owner")
        ]
        indexes = [models.Index(fields=["owner", "-created_at"])]

    def __str__(self):
        return f"{self.name} ({self.district})"


class CropRecord(models.Model):
    """One crop grown on a farm in a given season."""

    class Season(models.TextChoices):
        KHARIF = "kharif", "Kharif (monsoon)"
        RABI = "rabi", "Rabi (winter)"
        ZAID = "zaid", "Zaid (summer)"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        GROWING = "growing", "Growing"
        HARVESTED = "harvested", "Harvested"

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name="crop_records")
    crop_name = models.CharField(max_length=100)
    season = models.CharField(max_length=10, choices=Season.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    sowing_date = models.DateField(null=True, blank=True)
    expected_harvest_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["farm", "-created_at"])]

    def __str__(self):
        return f"{self.crop_name} ({self.season}) on {self.farm.name}"