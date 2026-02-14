from django.db import models

from documents.models import Document

ANALYSIS_JOB_STATUS_CHOICES = (
    ("PENDING", "Pending"),
    ("PROCESSING", "Processing"),
    ("READY", "Ready"),
    ("FAILED", "Failed"),
)

JOB_TYPE_CHOICES = (
    ("PREVIEW", "Preview"),
    ("FULL", "Full"),
)


class AnalysisJob(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="jobs"
    )
    job_type = models.CharField(
        max_length=10,
        choices=JOB_TYPE_CHOICES,
    )

    status = models.CharField(
        max_length=20,
        choices=ANALYSIS_JOB_STATUS_CHOICES,
        default="PENDING",
    )
    progress = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
