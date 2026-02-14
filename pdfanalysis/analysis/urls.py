from django.urls import path

from analysis.views import DocumentFullAnalysisCreateAPIView

urlpatterns = [
    path(
        "full-analysis/<int:id>/",
        DocumentFullAnalysisCreateAPIView.as_view(),
        name="analysis-full",
    ),
]
