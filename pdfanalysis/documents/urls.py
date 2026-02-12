from django.urls import path
from documents.views import(
     DocumentChunkListAPIView, 
     DocumentDetailAPIView, 
     DocumentListAPIView, 
     DocumentCreateAPIView,
     DocumentRecentListAPIView, 
     DocumentUpdateAPIView,
     DocumentOverviewAPIView,
     EventLogListAPIView
)

urlpatterns = [
    path("list/", DocumentListAPIView.as_view(), name="document-list"),
    
    path("create/", DocumentCreateAPIView.as_view(), name="document-create"),
    
    path("detail/<int:id>/", DocumentDetailAPIView.as_view(), name="document-detail"),

    path("update/<int:id>/", DocumentUpdateAPIView.as_view(), name="document-update"),
    
    path("chunks/<int:id>/", DocumentChunkListAPIView.as_view(), name="document-chunks"),
    
    path("overview/", DocumentOverviewAPIView.as_view(), name="document-overview"),
    
    path("recent-documents/", DocumentRecentListAPIView.as_view(), name="recent-documents"),
    
    path("event-log/", EventLogListAPIView.as_view(), name="event-log"),
    
]
