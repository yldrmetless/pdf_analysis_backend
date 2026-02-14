from django.urls import path

from documents.views import (
    DocumentCreateAPIView,
    DocumentDeleteAPIView,
    DocumentListAPIView,
    DocumentOverviewAPIView,
    DocumentRecentListAPIView,
    EventLogListAPIView,
    SignedUploadURLAPIView,
)

urlpatterns = [
    path("create/", DocumentCreateAPIView.as_view(), name="document-create"),
    path("list/", DocumentListAPIView.as_view(), name="document-list"),
    path("delete/<int:id>/", DocumentDeleteAPIView.as_view(), name="document-delete"),
    path("overview/", DocumentOverviewAPIView.as_view(), name="document-overview"),
    path(
        "recent-documents/",
        DocumentRecentListAPIView.as_view(),
        name="recent-documents",
    ),
    path("event-log/", EventLogListAPIView.as_view(), name="event-log"),
    path(
        "supabase/signed-upload/",
        SignedUploadURLAPIView.as_view(),
        name="signed-upload",
    ),
]
