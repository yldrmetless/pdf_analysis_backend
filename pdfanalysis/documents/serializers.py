from rest_framework import serializers
from documents.models import Document, DocumentChunk
from django.utils import timezone
from datetime import timedelta


class DocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ("title", "original_name", "file_path", "file_size", "mime_type", "checksum")
        
    def validate(self, attrs):
        user = self.context["request"].user
        
        time_threshold = timezone.now() - timedelta(days=1)
        DAILY_LIMIT = 15

        daily_upload_count = Document.objects.filter(
            owner=user, 
            created_at__gte=time_threshold,
            is_deleted=False
        ).count()

        if daily_upload_count >= DAILY_LIMIT:
            raise serializers.ValidationError({
                "error": f"Daily upload limit reached ({DAILY_LIMIT}). Please try again tomorrow."
            })
            
        return attrs

    def validate_mime_type(self, value):
        if value != "application/pdf":
            raise serializers.ValidationError("Only PDF files are accepted.")
        return value

    def validate_file_size(self, value):
        max_mb = 20
        if value > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File size must be at most {max_mb}MB.")
        return value

    def validate_file_path(self, value):
        if not value or ".." in value:
            raise serializers.ValidationError("Invalid file_path.")
        return value

    def create(self, validated_data):
        user = self.context["request"].user
        return Document.objects.create(owner=user, **validated_data)


class DocumentSerializer(serializers.ModelSerializer):
    latest_preview_job_status = serializers.SerializerMethodField()
    latest_preview_job_progress = serializers.SerializerMethodField()
    latest_preview_job_error = serializers.SerializerMethodField()
    chunk_count = serializers.SerializerMethodField()

    
    class Meta:
        model = Document
        fields = (
            "id", "title", "original_name", "file_path", "file_size", "mime_type",
            "status", "page_count", "language","preview_text", "created_at",
            "latest_preview_job_status", "latest_preview_job_progress", "latest_preview_job_error",
            "chunk_count"
        )

    def _latest_preview_job(self, obj):
        return (
            obj.jobs
            .filter(job_type="PREVIEW")
            .order_by("-id")
            .first()
        )

    def get_latest_preview_job_status(self, obj):
        job = self._latest_preview_job(obj)
        return job.status if job else None

    def get_latest_preview_job_progress(self, obj):
        job = self._latest_preview_job(obj)
        return job.progress if job else None

    def get_latest_preview_job_error(self, obj):
        job = self._latest_preview_job(obj)
        return job.error if job else ""
    
    def get_chunk_count(self, obj):
        return DocumentChunk.objects.filter(document=obj).count()
    
class DocumentOverviewSerializer(serializers.Serializer):
    total_documents = serializers.IntegerField()
    processing = serializers.IntegerField()
    ready = serializers.IntegerField()
    errors = serializers.IntegerField()



class RecentDocumentItemSerializer(serializers.ModelSerializer):
    document_name = serializers.SerializerMethodField()
    uploaded_at = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Document
        fields = ("id", "document_name", "status", "uploaded_at")

    def get_document_name(self, obj):
        return obj.title or obj.original_name
    
    
class EventLogItemSerializer(serializers.Serializer):
    ts = serializers.DateTimeField()
    event = serializers.CharField()
    detail = serializers.CharField()
    document_id = serializers.IntegerField(allow_null=True)