from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from documents.models import Document
from analysis.models import AnalysisJob
from analysis.tasks import run_full_analysis
from analysis.serializers import QARequestSerializer
import os
class DocumentFullAnalysisCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        doc = Document.objects.filter(
            id=id, owner=request.user, is_deleted=False
        ).first()

        if not doc:
            return Response(
                {"message": "Doküman bulunamadı.", "status": 404},
                status=status.HTTP_404_NOT_FOUND
            )

        existing = AnalysisJob.objects.filter(
            document=doc,
            job_type="FULL",
            status__in=["PENDING", "PROCESSING"],
        ).exists()
        if existing:
            return Response(
                {"message": "Full analysis zaten sırada veya çalışıyor.", "status": 409},
                status=status.HTTP_409_CONFLICT
            )

        job = AnalysisJob.objects.create(
            document=doc,
            job_type="FULL",
            status="PENDING",
            progress=0,
        )

        doc.status = "PROCESSING"
        doc.save(update_fields=["status"])
        
        run_full_analysis.delay(job.id)

        return Response(
            {
                "status": 201,
                "message": "Full analysis job oluşturuldu.",
                "job": {
                    "id": job.id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "progress": job.progress,
                    "created_at": job.created_at,
                },
            },
            status=status.HTTP_201_CREATED
        )
        
        
    def get(self, request, id):
        doc = Document.objects.filter(
            id=id,
            owner=request.user,
            is_deleted=False
        ).first()

        if not doc:
            return Response(
                {"status": 404, "message": "Doküman bulunamadı."},
                status=404
            )

        job = (
            AnalysisJob.objects
            .filter(document=doc, job_type="FULL")
            .order_by("-id")
            .first()
        )

        return Response({
            "status": 200,

            # -------- DOCUMENT DATA --------
            "document": {
                "id": doc.id,
                "title": doc.title,
                "original_name": doc.original_name,
                "created_at": doc.created_at,
                "file_size": doc.file_size,
                "document_status": doc.status,
                "page_count": doc.page_count,
            },

            # -------- ANALYSIS DATA --------
            "analysis": {
                "analysis_text": doc.analysis_text,
                "analysis_json": doc.analysis_json,
                "ai_raw": doc.ai_raw,
            },

            # -------- JOB DATA --------
            "job": {
                "id": job.id if job else None,
                "status": job.status if job else None,
                "progress": job.progress if job else None,
                "error": job.error if job else None,
                "finished_at": job.finished_at if job else None,
            }

        }, status=200)
