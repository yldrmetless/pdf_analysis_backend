from django.urls import path
from analysis.views import DocumentFullAnalysisCreateAPIView, DocumentPreviewAPIView, DocumentQAAPIView

urlpatterns = [
    path("preview/<int:id>/", DocumentPreviewAPIView.as_view(), name="preview"),
    
    path("full-analysis/<int:id>/", DocumentFullAnalysisCreateAPIView.as_view(), name="analysis-full"),
    
    path("qa/<int:id>/", DocumentQAAPIView.as_view(), name="analysis-qa"),
    
]