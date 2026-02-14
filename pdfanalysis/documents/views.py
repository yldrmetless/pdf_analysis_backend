import os
import re
import unicodedata

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from supabase import Client, create_client

from analysis.models import AnalysisJob
from documents.models import Document
from documents.paginations import Pagination10
from documents.serializers import (
    DocumentCreateSerializer,
    DocumentOverviewSerializer,
    DocumentSerializer,
    EventLogItemSerializer,
    RecentDocumentItemSerializer,
)


class DocumentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DocumentCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = Document.objects.filter(owner=request.user, is_deleted=False).order_by(
            "-id"
        )

        name_filter = request.query_params.get("name", None)
        if name_filter:
            qs = qs.filter(original_name__icontains=name_filter)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        serializer = DocumentSerializer(page, many=True)
        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {"status": 200, **paginated_response.data}, status=status.HTTP_200_OK
        )


class DocumentDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        doc = Document.objects.filter(
            id=id, owner=request.user, is_deleted=False
        ).first()

        if not doc:
            return Response(
                {"detail": "Document not found."}, status=status.HTTP_404_NOT_FOUND
            )
        doc.is_deleted = True
        doc.save(update_fields=["is_deleted"])

        return Response(
            {"message": "Document deleted.", "status": 200}, status=status.HTTP_200_OK
        )


class DocumentOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Document.objects.filter(owner=request.user, is_deleted=False)

        ready_statuses = ["READY", "PREVIEW_READY"]
        processing_statuses = ["PROCESSING"]
        error_statuses = ["FAILED"]

        agg = qs.aggregate(
            total_documents=Count("id"),
            processing=Count("id", filter=Q(status__in=processing_statuses)),
            ready=Count("id", filter=Q(status__in=ready_statuses)),
            errors=Count("id", filter=Q(status__in=error_statuses)),
        )

        serializer = DocumentOverviewSerializer(agg)

        return Response(
            {"status": 200, "results": serializer.data}, status=status.HTTP_200_OK
        )


class SignedUploadURLAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_name = request.data.get("file_name")
        content_type = request.data.get("content_type")
        file_size = request.data.get("file_size")

        if not file_name or not content_type:
            return Response(
                {"detail": "file_name and content_type are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if content_type != "application/pdf":
            return Response(
                {"detail": "Only application/pdf is allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if file_size and int(file_size) > 50 * 1024 * 1024:
            return Response(
                {"detail": "File size exceeds 50MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def normalize_filename(name):
            name = (
                unicodedata.normalize("NFKD", name)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            name = name.replace(" ", "_")
            name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
            return name

        safe_name = normalize_filename(file_name)

        storage_path = f"uploads/{safe_name}"

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        bucket = os.getenv("SUPABASE_BUCKET", "")

        if not url or not key or not bucket:
            return Response(
                {"detail": "Server configuration error: Missing Supabase credentials."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        supabase: Client = create_client(url, key)

        try:
            try:
                supabase.storage.from_(bucket).remove([storage_path])
            except Exception:
                pass

            res = supabase.storage.from_(bucket).create_signed_upload_url(storage_path)

            signed_url = None
            token = None

            if isinstance(res, dict):
                signed_url = res.get("signed_url") or res.get("signedURL")
                token = res.get("token")
            else:
                signed_url = getattr(res, "signed_url", None) or getattr(
                    res, "signedURL", None
                )
                token = getattr(res, "token", None)

            if not signed_url:
                return Response(
                    {"detail": "Failed to generate signed URL."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "status": 200,
                    "results": {
                        "bucket": bucket,
                        "path": storage_path,
                        "token": token,
                        "signed_url": signed_url,
                        "method": "PUT",
                        "headers": {"Content-Type": "application/pdf"},
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentRecentListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = Document.objects.filter(owner=request.user, is_deleted=False).order_by(
            "-created_at"
        )

        document_name_filter = request.query_params.get("document_name", None)
        if document_name_filter:
            qs = qs.filter(
                Q(title__icontains=document_name_filter)
                | Q(original_name__icontains=document_name_filter)
            )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        serializer = RecentDocumentItemSerializer(page, many=True)

        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {"status": 200, **paginated_response.data}, status=status.HTTP_200_OK
        )


class EventLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = (
            AnalysisJob.objects.filter(document__owner=request.user)
            .select_related("document")
            .order_by("-created_at")
        )

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        results = [
            {
                "ts": j.created_at,
                "event": j.status,
                "detail": f"{j.job_type} job {j.status}",
                "document_id": j.document_id,
            }
            for j in page
        ]

        serializer = EventLogItemSerializer(results, many=True)

        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {"status": 200, **paginated_response.data}, status=status.HTTP_200_OK
        )
