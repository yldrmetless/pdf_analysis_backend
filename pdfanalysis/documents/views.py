from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from documents.models import Document,DocumentChunk
from documents.serializers import (
    DocumentCreateSerializer, 
    DocumentOverviewSerializer, 
    DocumentSerializer, 
    DocumentChunkSerializer,
    EventLogItemSerializer,
    RecentDocumentItemSerializer
)
from rest_framework.permissions import IsAuthenticated
from documents.paginations import Pagination10
from analysis.models import AnalysisJob
from django.db.models import Count, Q

class DocumentListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = Document.objects.filter(
            owner=request.user,
            is_deleted=False
        ).order_by("-id")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        serializer = DocumentSerializer(page, many=True)

        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {
                "status": 200,
                **paginated_response.data
            },
            status=status.HTTP_200_OK
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
    
    
class DocumentDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        doc = (
            Document.objects
            .filter(id=id, owner=request.user, is_deleted=False)
            .prefetch_related("jobs")
            .first()
        )

        if not doc:
            return Response(
                {"status": 404, "message": "Doküman bulunamadı."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "status": 200,
                "results": DocumentSerializer(doc).data
            },
            status=status.HTTP_200_OK
        )

        
        

class DocumentUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, id):
        doc = Document.objects.filter(
            id=id,
            owner=request.user,
            is_deleted=False
        ).first()

        if not doc:
            return Response(
                {"detail": "Doküman bulunamadı."},
                status=status.HTTP_404_NOT_FOUND
            )
        doc.is_deleted = True
        doc.save(update_fields=["is_deleted"])

        return Response(
            {"message": "Doküman silindi.", "status": 200},
            status=status.HTTP_200_OK
        )
        
        

class DocumentChunkListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        doc = Document.objects.filter(
            id=id,
            owner=request.user,
            is_deleted=False
        ).first()

        if not doc:
            return Response(
                {"message": "Doküman bulunamadı.", "status": 404},
                status=status.HTTP_404_NOT_FOUND
            )

        queryset = DocumentChunk.objects.filter(
            document=doc
        ).order_by("chunk_index")

        paginator = Pagination10()
        page = paginator.paginate_queryset(queryset, request)

        serializer = DocumentChunkSerializer(page, many=True)

        return paginator.get_paginated_response({
            "status": 200,
            "results": serializer.data
        })
        


class DocumentOverviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Document.objects.filter(
            owner=request.user,
            is_deleted=False
        )

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
            {
                "status": 200,
                "results": serializer.data
            },
            status=status.HTTP_200_OK
        )
        

class DocumentRecentListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = Document.objects.filter(
            owner=request.user,
            is_deleted=False
        ).order_by("-created_at")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)

        serializer = RecentDocumentItemSerializer(page, many=True)

        paginated_response = paginator.get_paginated_response(serializer.data)

        return Response(
            {
                "status": 200,
                **paginated_response.data
            },
            status=status.HTTP_200_OK
        )



class EventLogListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination10

    def get(self, request):
        qs = (
            AnalysisJob.objects
            .filter(document__owner=request.user)
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
            {
                "status": 200,
                **paginated_response.data
            },
            status=status.HTTP_200_OK
        )