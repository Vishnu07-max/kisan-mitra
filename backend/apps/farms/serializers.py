from rest_framework import serializers

from .models import CropRecord, Farm


class FarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = Farm
        fields = [
            "id", "name", "state", "district", "latitude", "longitude",
            "soil_type", "irrigation_type", "area_acres", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        user = self.context["request"].user
        qs = Farm.objects.filter(owner=user, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("You already have a farm with this name.")
        return value

    def validate(self, attrs):
        lat = attrs.get("latitude", getattr(self.instance, "latitude", None))
        lon = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (lat is None) != (lon is None):
            raise serializers.ValidationError(
                "Provide both latitude and longitude, or leave both empty."
            )
        return attrs


class CropRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CropRecord
        fields = [
            "id", "crop_name", "season", "status", "sowing_date",
            "expected_harvest_date", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        sowing = attrs.get("sowing_date", getattr(self.instance, "sowing_date", None))
        harvest = attrs.get(
            "expected_harvest_date", getattr(self.instance, "expected_harvest_date", None)
        )
        if sowing and harvest and harvest < sowing:
            raise serializers.ValidationError(
                {"expected_harvest_date": ["Harvest date cannot be before sowing date."]}
            )
        return attrs