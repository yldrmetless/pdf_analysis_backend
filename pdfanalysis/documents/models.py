from django.db import models

from accounts.models import User

# Create your models here.
DOCUMENT_STATUS_CHOICES = (
    ("UPLOADED", "Uploaded"),
    ("PREVIEW_READY", "Preview Ready"),
    ("PROCESSING", "Processing"),
    ("READY", "Ready"),
    ("FAILED", "Failed"),
)


class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=255, blank=True)
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    file_size = models.BigIntegerField()
    mime_type = models.CharField(max_length=120)

    page_count = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=20, blank=True)

    preview_text = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=DOCUMENT_STATUS_CHOICES,
        default="UPLOADED",
    )
    checksum = models.CharField(max_length=64, db_index=True)

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    analysis_json = models.JSONField(null=True, blank=True)
    analysis_text = models.TextField(blank=True, default="")

    ai_raw = models.TextField(blank=True, default="")


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="chunks"
    )
    chunk_index = models.PositiveIntegerField()

    page_start = models.PositiveIntegerField()
    page_end = models.PositiveIntegerField()
    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("document", "chunk_index")
        ordering = ["chunk_index"]
