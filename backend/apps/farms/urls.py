from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import FarmCropDetailView, FarmCropListCreateView, FarmViewSet

router = SimpleRouter()
router.register("farms", FarmViewSet, basename="farm")

urlpatterns = router.urls + [
    path("farms/<int:farm_id>/crops/", FarmCropListCreateView.as_view(), name="farm-crops"),
    path("farms/<int:farm_id>/crops/<int:pk>/", FarmCropDetailView.as_view(), name="farm-crop-detail"),
]