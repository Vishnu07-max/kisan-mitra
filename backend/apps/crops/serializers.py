import math

from rest_framework import serializers

from .inference import FEATURES
from .models import Recommendation

NUTRIENTS = ["N", "P", "K"]
CLIMATE = ["temperature", "humidity", "rainfall"]


class RecommendInputSerializer(serializers.Serializer):
    N = serializers.FloatField(required=False, min_value=0, max_value=500)
    P = serializers.FloatField(required=False, min_value=0, max_value=500)
    K = serializers.FloatField(required=False, min_value=0, max_value=500)
    ph = serializers.FloatField(required=False, min_value=0, max_value=14)
    temperature = serializers.FloatField(required=False, min_value=-10, max_value=60)
    humidity = serializers.FloatField(required=False, min_value=0, max_value=100)
    rainfall = serializers.FloatField(required=False, min_value=0, max_value=3000)
    farm_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        errors = {}
        for f in FEATURES:
            if f in attrs and not math.isfinite(attrs[f]):
                errors[f] = ["Enter a valid number."]
        for cols in (NUTRIENTS, CLIMATE):
            have = [c for c in cols if c in attrs]
            if have and len(have) != len(cols):
                for c in cols:
                    if c not in attrs:
                        errors[c] = [f"Give all of {', '.join(cols)} together, or none of them."]
        if errors:
            raise serializers.ValidationError(errors)

        has_nutrients = all(c in attrs for c in NUTRIENTS)
        has_climate = all(c in attrs for c in CLIMATE)
        if not (has_nutrients or has_climate):
            raise serializers.ValidationError(
                {"non_field_errors": [
                    "Enter N, P and K, or temperature, humidity and rainfall. "
                    "Soil pH alone is not enough to suggest a crop."
                ]}
            )
        return attrs


class RecommendationSerializer(serializers.ModelSerializer):
    farm_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Recommendation
        fields = ["id", "inputs", "input_set", "suggestions", "warnings", "model_version", "farm_id", "created_at"]
        read_only_fields = fields