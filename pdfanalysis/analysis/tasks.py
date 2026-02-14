import re

from celery import shared_task
from django.utils import timezone

from analysis.helpers.ai_analysis import (
    analyze_document_with_openai,
    generate_suggestions_en,
)
from analysis.models import AnalysisJob
from analysis.services import (
    download_pdf_bytes_from_supabase,
    extract_full_text_pages,
)
from documents.models import DocumentChunk


def sanitize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\x00", "")
    s = re.sub(r"[\x01-\x08\x0B\x0C\x0E-\x1F]", "", s)
    return s


def deep_sanitize(obj):
    if isinstance(obj, str):
        return sanitize_text(obj)
    if isinstance(obj, list):
        return [deep_sanitize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: deep_sanitize(v) for k, v in obj.items()}
    return obj


@shared_task(bind=True)
def run_full_analysis(self, job_id: int):
    enable_suggestions = True
    job = AnalysisJob.objects.select_related("document").get(id=job_id)
    doc = job.document

    try:
        job.status = "PROCESSING"
        job.started_at = timezone.now()
        job.progress = 0
        job.error = ""
        job.save(update_fields=["status", "started_at", "progress", "error"])

        pdf_bytes = download_pdf_bytes_from_supabase(doc.file_path)
        page_count, pages = extract_full_text_pages(pdf_bytes, max_pages=50)

        DocumentChunk.objects.filter(document=doc).delete()

        chunk_index = 0
        total = len(pages)

        for i in range(0, total, 2):
            page_start = i + 1
            page_end = min(i + 2, total)

            text = "\n\n".join([t for t in pages[i:page_end] if t]).strip()
            text = sanitize_text(text)
            if text:
                DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    text=text,
                )
                chunk_index += 1

            job.progress = min(95, int((page_end / max(1, total)) * 95))
            job.save(update_fields=["progress"])

        job.progress = 99
        job.save(update_fields=["progress"])

        full_text = "\n\n".join([t for t in pages if t]).strip()
        full_text = sanitize_text(full_text)

        raw, analysis = analyze_document_with_openai(full_text)
        raw = sanitize_text(raw)
        analysis = deep_sanitize(analysis)

        analysis.pop("suggestions", None)

        if enable_suggestions:
            raw_retry, analysis_retry = generate_suggestions_en(full_text)
            analysis_retry = deep_sanitize(analysis_retry) or {}
            retry_sugs = analysis_retry.get("suggestions", [])
            if isinstance(retry_sugs, list) and len(retry_sugs) > 0:
                analysis["suggestions"] = retry_sugs
            else:
                analysis["suggestions"] = []
        else:
            analysis["suggestions"] = []

        doc.ai_raw = raw
        doc.analysis_json = analysis
        doc.analysis_text = analysis.get("summary", "")
        # ---- AI ANALYSIS (BİTTİ) ----

        doc.page_count = page_count
        doc.status = "READY"
        doc.save(
            update_fields=[
                "page_count",
                "status",
                "ai_raw",
                "analysis_json",
                "analysis_text",
            ]
        )

        job.status = "READY"
        job.progress = 100
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "progress", "finished_at"])

    except Exception as e:
        doc.status = "FAILED"
        doc.save(update_fields=["status"])

        job.status = "FAILED"
        job.progress = 100
        job.finished_at = timezone.now()
        job.error = str(e)
        job.save(update_fields=["status", "progress", "finished_at", "error"])
