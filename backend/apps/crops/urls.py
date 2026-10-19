from django.urls import path

from .views import RecommendationDetailView, RecommendationListView, RecommendView

urlpatterns = [
    path("crops/recommend/", RecommendView.as_view(), name="crop-recommend"),
    path("crops/recommendations/", RecommendationListView.as_view(), name="recommendation-list"),
    path("crops/recommendations/<int:pk>/", RecommendationDetailView.as_view(), name="recommendation-detail"),
]