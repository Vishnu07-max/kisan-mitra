from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.farms.models import Farm

from .alerts import build_alerts
from .client import WeatherUnavailable, fetch_forecast
from .serializers import ForecastQuerySerializer


class WeatherServiceError(APIException):
    status_code = 502
    default_detail = "The weather service could not be reached. Please try again."
    default_code = "weather_unavailable"


class ForecastView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "weather"

    def get(self, request):
        ser = ForecastQuerySerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        q = ser.validated_data

        farm = None
        if "farm_id" in q:
            farm = Farm.objects.filter(pk=q["farm_id"], owner=request.user).first()
            if farm is None:
                raise ValidationError({"farm_id": ["Unknown farm."]})
            if farm.latitude is None or farm.longitude is None:
                raise ValidationError(
                    {"farm_id": ["This farm has no coordinates. Add latitude and longitude to the farm first."]}
                )
            lat, lon = float(farm.latitude), float(farm.longitude)
        else:
            lat, lon = q["lat"], q["lon"]

        # About 1 km: the exact farm position is never sent to the weather service
        lat, lon = round(lat, 2), round(lon, 2)

        key = f"weather:{lat}:{lon}"
        entry = cache.get(key)
        from_cache = entry is not None
        if entry is None:
            try:
                forecast = fetch_forecast(lat, lon)
            except WeatherUnavailable:
                raise WeatherServiceError()
            entry = {"forecast": forecast, "fetched_at": timezone.now().isoformat()}
            cache.set(key, entry, settings.WEATHER_CACHE_SECONDS)

        forecast = entry["forecast"]
        return Response({
            "location": {"latitude": lat, "longitude": lon, "farm_id": farm.id if farm else None},
            "timezone": forecast["timezone"],
            "current": forecast["current"],
            "daily": forecast["daily"],
            "alerts": build_alerts(forecast["daily"]),
            "fetched_at": entry["fetched_at"],
            "from_cache": from_cache,
            "notes": {
                "daily_is_forecast": True,
                "current_is_model_estimate": True,
                "alerts_are_general_guidance": True,
            },
            "source": {"name": "Open-Meteo.com", "url": "https://open-meteo.com/"},
        })