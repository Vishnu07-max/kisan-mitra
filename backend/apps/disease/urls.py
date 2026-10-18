from django.urls import path

from .views import AssessmentDetailView, AssessmentImageView, AssessmentListView, PredictView

urlpatterns = [
    path("disease/predict/", PredictView.as_view(), name="disease-predict"),
    path("disease/assessments/", AssessmentListView.as_view(), name="assessment-list"),
    path("disease/assessments/<int:pk>/", AssessmentDetailView.as_view(), name="assessment-detail"),
    path("disease/assessments/<int:pk>/image/", AssessmentImageView.as_view(), name="assessment-image"),
]