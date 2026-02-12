from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from documents.models import Document
from analysis.models import AnalysisJob
from analysis.services import (
    download_pdf_bytes_from_supabase, extract_first_pages_text, retrieve_top_chunks, build_context, answer_mock, answer_with_openai
)
from analysis.tasks import run_full_analysis
from analysis.serializers import QARequestSerializer
import os
from accounts.services import consume_qa_quota, QuotaExceeded

class DocumentPreviewAPIView(APIView):
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
        refresh = request.query_params.get("refresh") == "1"
        if doc.preview_text and doc.status == "PREVIEW_READY" and not refresh:
            return Response(
                {
                    "status": 200,
                    "document_status": doc.status,
                    "page_count": doc.page_count,
                    "preview_text": doc.preview_text,
                },
                status=status.HTTP_200_OK
            )

        existing = AnalysisJob.objects.filter(
            document=doc,
            job_type="PREVIEW",
            status__in=["PENDING", "PROCESSING"]
        ).exists()

        if existing:
            return Response(
                {"message": "Preview zaten sırada veya çalışıyor.", "status": 409},
                status=status.HTTP_409_CONFLICT
            )

        job = AnalysisJob.objects.create(
            document=doc,
            job_type="PREVIEW",
            status="PROCESSING",
            progress=0,
            started_at=timezone.now(),
        )

        try:
            pdf_bytes = download_pdf_bytes_from_supabase(doc.file_path)
            page_count, preview_text = extract_first_pages_text(pdf_bytes, max_pages=2)

            doc.page_count = page_count
            doc.preview_text = preview_text or ""
            doc.status = "PREVIEW_READY" if preview_text else "FAILED"
            doc.save(update_fields=["page_count", "preview_text", "status"])

            job.status = "READY" if preview_text else "FAILED"
            job.progress = 100
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "progress", "finished_at"])

            return Response(
                {
                    "status": 200,
                    "document_status": doc.status,
                    "page_count": page_count,
                    "preview_text": doc.preview_text,
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            doc.status = "FAILED"
            doc.save(update_fields=["status"])

            job.status = "FAILED"
            job.progress = 100
            job.error = str(e)
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "progress", "error", "finished_at"])

            return Response(
                {"message": "Preview sırasında hata oluştu.", "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



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
        doc = Document.objects.filter(id=id, owner=request.user, is_deleted=False).first()
        if not doc:
            return Response({"status": 404, "message": "Doküman bulunamadı."}, status=404)

        job = (AnalysisJob.objects
               .filter(document=doc, job_type="FULL")
               .order_by("-id")
               .first())

        return Response({
            "status": 200,
            "document_status": doc.status,   # READY/FAILED/PROCESSING
            "page_count": doc.page_count,
            "analysis_text": getattr(doc, "analysis_text", ""),
            "analysis_json": getattr(doc, "analysis_json", None),
            "ai_raw": getattr(doc, "ai_raw", ""),   # <-- burada DOLU gelecek
            "job": {
                "id": job.id if job else None,
                "status": job.status if job else None,
                "progress": job.progress if job else None,
                "error": job.error if job else None,
                "finished_at": job.finished_at if job else None,
            }
        }, status=200)
        
        

class DocumentQAAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        doc = Document.objects.filter(id=id, owner=request.user, is_deleted=False).first()
        if not doc:
            return Response(
                {"message": "Doküman bulunamadı.", "status": 404},
                status=status.HTTP_404_NOT_FOUND
            )

        ser = QARequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        question = ser.validated_data["question"]
        
        try:
            consume_qa_quota(request.user, daily_limit=30)
        except QuotaExceeded as e:
            return Response(
                {"message": str(e), "status": 429},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        top_k = int(os.getenv("QA_TOP_K", "4"))
        max_chars = int(os.getenv("QA_MAX_CHARS", "8000"))

        chunks = retrieve_top_chunks(doc.id, question, top_k=top_k)
        context = build_context(chunks, max_chars=max_chars)

        ai_mode = os.getenv("AI_MODE", "mock").lower().strip()
        try:
            if ai_mode == "real":
                answer = answer_with_openai(question, context)
            else:
                answer = answer_mock(question, chunks)
        except Exception as e:
            return Response(
                {"message": "QA sırasında hata oluştu.", "error": str(e), "status": 500},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        sources = [
            {"chunk_index": c.chunk_index, "page_start": c.page_start, "page_end": c.page_end}
            for c in chunks
        ]

        return Response(
            {"status": 200, "answer": answer, "sources": sources},
            status=status.HTTP_200_OK
        )
