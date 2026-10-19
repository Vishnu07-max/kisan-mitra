import math

from rest_framework import serializers


class ForecastQuerySerializer(serializers.Serializer):
    farm_id = serializers.IntegerField(required=False)
    lat = serializers.FloatField(required=False, min_value=-90, max_value=90)
    lon = serializers.FloatField(required=False, min_value=-180, max_value=180)

    def validate(self, attrs):
        for key in ("lat", "lon"):
            if key in attrs and not math.isfinite(attrs[key]):
                raise serializers.ValidationError({key: ["Enter a valid number."]})
        if ("lat" in attrs) != ("lon" in attrs):
            raise serializers.ValidationError({"lat": ["Give both lat and lon."]})
        has_point = "lat" in attrs
        if "farm_id" not in attrs and not has_point:
            raise serializers.ValidationError({"non_field_errors": ["Give farm_id, or lat and lon."]})
        if "farm_id" in attrs and has_point:
            raise serializers.ValidationError({"non_field_errors": ["Give either farm_id or lat and lon, not both."]})
        return attrs