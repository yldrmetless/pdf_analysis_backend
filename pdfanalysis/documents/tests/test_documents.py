from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from analysis.models import AnalysisJob
from documents.models import Document

User = get_user_model()


@pytest.fixture
def api_client():
    """Tüm testlerde kullanılabilecek merkezi API istemcisi."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Merkezi test kullanıcısı fixture'ı."""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="metehany",
        email="mete@yildirim.com",
        password="password123",
    )


########## DOCUMENT CREATE TEST ################
@pytest.mark.django_db
class TestDocumentCreate:
    url = reverse("document-create")

    def test_create_document_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        payload = {
            "title": "My Resume",
            "original_name": "resume.pdf",
            "file_path": "uploads/resume.pdf",
            "file_size": 1024 * 1024,
            "mime_type": "application/pdf",
            "checksum": "abc123checksum",
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == payload["title"]
        assert Document.objects.filter(owner=test_user, title="My Resume").exists()

    def test_create_document_invalid_mime(self, api_client, test_user):
        """PDF dışındaki dosya türlerinin reddedilmesi testi."""
        api_client.force_authenticate(user=test_user)

        payload = {
            "title": "Image File",
            "original_name": "photo.jpg",
            "file_path": "uploads/photo.jpg",
            "file_size": 500,
            "mime_type": "image/jpeg",
            "checksum": "check123",
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only PDF files are accepted." in str(response.data)

    def test_create_document_size_limit(self, api_client, test_user):
        """20MB limitinin üzerindeki dosyaların reddedilmesi testi."""
        api_client.force_authenticate(user=test_user)

        max_size = 21 * 1024 * 1024
        payload = {
            "title": "Large File",
            "file_size": max_size,
            "mime_type": "application/pdf",
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File size must be at most 20MB." in str(response.data)

    def test_daily_upload_limit(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        for i in range(15):
            Document.objects.create(
                owner=test_user,
                title=f"Doc {i}",
                original_name=f"test_{i}.pdf",
                file_path=f"uploads/test_{i}.pdf",
                mime_type="application/pdf",
                file_size=100,
                checksum=f"hash_{i}",
            )

        payload = {
            "title": "16th Doc",
            "original_name": "16th.pdf",
            "file_path": "uploads/16th.pdf",
            "mime_type": "application/pdf",
            "file_size": 100,
            "checksum": "final_hash",
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Daily upload limit reached" in str(response.data)

    def test_create_document_unauthenticated(self, api_client):
        """Yetkisiz erişimin engellenmesi testi."""
        response = api_client.post(self.url, {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


########### DOCUMENT LIST TESTS ############
@pytest.mark.django_db
class TestDocumentList:
    url = reverse("document-list")

    def test_list_documents_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        for i in range(3):
            Document.objects.create(
                owner=test_user,
                title=f"Doc {i}",
                original_name=f"file_{i}.pdf",
                file_path=f"uploads/file_{i}.pdf",
                file_size=1024,
                mime_type="application/pdf",
                checksum=f"hash_{i}",
            )
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_documents_owner_isolation(self, api_client, test_user):
        other_user = get_user_model().objects.create_user(
            username="otheruser", email="other@test.com", password="pass"
        )
        Document.objects.create(
            owner=other_user,
            title="Other Doc",
            original_name="other.pdf",
            file_size=1024,  # Zorunlu alan eklendi
            mime_type="application/pdf",
        )
        api_client.force_authenticate(user=test_user)
        response = api_client.get(self.url)
        assert len(response.data["results"]) == 0

    def test_list_documents_exclude_deleted(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        Document.objects.create(
            owner=test_user, title="Active", file_size=1024, is_deleted=False
        )
        Document.objects.create(
            owner=test_user, title="Deleted", file_size=1024, is_deleted=True
        )
        response = api_client.get(self.url)
        assert len(response.data["results"]) == 1

    def test_list_documents_search_filter(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        Document.objects.create(
            owner=test_user, original_name="Metehan_CV.pdf", file_size=1024
        )
        Document.objects.create(
            owner=test_user, original_name="Report.pdf", file_size=1024
        )
        response = api_client.get(f"{self.url}?name=Mete")
        assert len(response.data["results"]) == 1

    def test_list_documents_pagination(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        for i in range(12):
            Document.objects.create(owner=test_user, title=f"D {i}", file_size=1024)
        response = api_client.get(self.url)
        assert response.data["count"] == 12
        assert len(response.data["results"]) == 10


######### DOCUMENT DELETE TESTS ############
@pytest.mark.django_db
class TestDocumentDelete:
    def test_delete_document_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        doc = Document.objects.create(
            owner=test_user, title="Delete Me", file_size=1024, is_deleted=False
        )

        url = reverse("document-delete", kwargs={"id": doc.id})
        response = api_client.patch(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Document deleted."

        doc.refresh_from_db()
        assert doc.is_deleted is True

    def test_delete_document_isolation(self, api_client, test_user):
        other_user = User.objects.create_user(
            username="other", email="other@test.com", password="pass"
        )
        other_doc = Document.objects.create(
            owner=other_user, title="Other's Doc", file_size=1024
        )

        api_client.force_authenticate(user=test_user)
        url = reverse("document-delete", kwargs={"id": other_doc.id})
        response = api_client.patch(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["detail"] == "Document not found."

        other_doc.refresh_from_db()
        assert other_doc.is_deleted is False

    def test_delete_non_existent_document(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        url = reverse("document-delete", kwargs={"id": 9999})
        response = api_client.patch(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_already_deleted_document(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        doc = Document.objects.create(
            owner=test_user, title="Already Deleted", is_deleted=True, file_size=1024
        )

        url = reverse("document-delete", kwargs={"id": doc.id})
        response = api_client.patch(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_document_unauthenticated(self, api_client):
        url = reverse("document-delete", kwargs={"id": 1})
        response = api_client.patch(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


############ DOCUMENT OVERVIEW TESTS ############
@pytest.mark.django_db
class TestDocumentOverview:
    url = reverse("document-overview")

    def test_get_overview_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        Document.objects.create(owner=test_user, status="READY", file_size=100)
        Document.objects.create(owner=test_user, status="PREVIEW_READY", file_size=100)
        Document.objects.create(owner=test_user, status="PROCESSING", file_size=100)
        Document.objects.create(owner=test_user, status="FAILED", file_size=100)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]

        assert results["total_documents"] == 4
        assert results["ready"] == 2
        assert results["processing"] == 1
        assert results["errors"] == 1

    def test_overview_isolation(self, api_client, test_user):
        """İstatistiklerin sadece giriş yapmış kullanıcıya özel olması testi."""
        from django.contrib.auth import get_user_model

        other_user = get_user_model().objects.create_user(
            username="other", email="other@test.com", password="pass"
        )
        Document.objects.create(owner=other_user, status="READY", file_size=100)

        Document.objects.create(owner=test_user, status="READY", file_size=100)

        api_client.force_authenticate(user=test_user)
        response = api_client.get(self.url)

        assert response.data["results"]["total_documents"] == 1

    def test_overview_exclude_deleted(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        Document.objects.create(
            owner=test_user, status="READY", is_deleted=False, file_size=100
        )
        Document.objects.create(
            owner=test_user, status="READY", is_deleted=True, file_size=100
        )

        response = api_client.get(self.url)

        assert response.data["results"]["total_documents"] == 1
        assert response.data["results"]["ready"] == 1

    def test_overview_unauthenticated(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


####### RECENT DOCUMENTS TESTS ############
@pytest.mark.django_db
class TestDocumentRecentList:
    """DocumentRecentListAPIView fonksiyonelliğini test eden sınıf."""

    url = reverse("recent-documents")

    def test_list_recent_documents_success(self, api_client, test_user):
        """Son dökümanların doğru sıralama (-created_at) ile gelmesi testi."""
        api_client.force_authenticate(user=test_user)

        doc1 = Document.objects.create(
            owner=test_user,
            title="Old Doc",
            file_size=100,
            created_at=timezone.now() - timedelta(days=1),
        )
        doc2 = Document.objects.create(
            owner=test_user, title="New Doc", file_size=100, created_at=timezone.now()
        )

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]

        assert results[0]["id"] == doc2.id
        assert results[1]["id"] == doc1.id

        assert results[0]["document_name"] == "New Doc"
        assert results[1]["document_name"] == "Old Doc"

    def test_recent_documents_search_filter(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        Document.objects.create(owner=test_user, title="Specific Title", file_size=100)
        Document.objects.create(
            owner=test_user, original_name="specific_file.pdf", file_size=100
        )
        Document.objects.create(
            owner=test_user, title="Other", original_name="other.pdf", file_size=100
        )

        response = api_client.get(f"{self.url}?document_name=Specific")

        assert len(response.data["results"]) == 2

    def test_recent_serializer_fields(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        doc = Document.objects.create(
            owner=test_user, title="", original_name="no_title.pdf", file_size=100
        )

        response = api_client.get(self.url)
        item = response.data["results"][0]

        assert item["id"] == doc.id
        assert item["document_name"] == "no_title.pdf"
        assert "uploaded_at" in item

    def test_recent_documents_isolation(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        Document.objects.create(
            owner=test_user, title="Deleted", is_deleted=True, file_size=100
        )
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(username="other2", password="123")
        Document.objects.create(owner=other, title="Other User Doc", file_size=100)

        response = api_client.get(self.url)
        assert len(response.data["results"]) == 0


######## EVENT LOG TESTS ############
@pytest.mark.django_db
class TestEventLogList:
    url = reverse("event-log")

    def test_list_event_log_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        doc = Document.objects.create(owner=test_user, title="Log Doc", file_size=100)

        job1 = AnalysisJob.objects.create(
            document=doc, job_type="PREVIEW", status="COMPLETED"
        )
        job2 = AnalysisJob.objects.create(
            document=doc, job_type="ANALYSIS", status="PROCESSING"
        )

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]

        assert len(results) == 2

        assert results[0]["event"] == job2.status
        assert results[1]["event"] == job1.status

        assert results[0]["detail"] == f"{job2.job_type} job {job2.status}"
        assert results[1]["detail"] == f"{job1.job_type} job {job1.status}"

        assert results[0]["document_id"] == doc.id

    def test_event_log_isolation(self, api_client, test_user):
        """Kullanıcıların sadece kendi dökümanlarına ait logları görmesi testi."""
        from django.contrib.auth import get_user_model

        other_user = get_user_model().objects.create_user(
            username="other_admin", email="admin@other.com", password="123"
        )
        other_doc = Document.objects.create(
            owner=other_user, title="Secret", file_size=100
        )
        AnalysisJob.objects.create(
            document=other_doc, job_type="PREVIEW", status="FAILED"
        )

        api_client.force_authenticate(user=test_user)
        response = api_client.get(self.url)

        assert len(response.data["results"]) == 0

    def test_event_log_pagination(self, api_client, test_user):
        """Pagination (10 kayıt sınırı) kontrolü."""
        api_client.force_authenticate(user=test_user)
        doc = Document.objects.create(owner=test_user, title="Page Doc", file_size=100)

        # 12 adet iş oluştur
        for i in range(12):
            AnalysisJob.objects.create(document=doc, job_type="PREVIEW", status="READY")

        response = api_client.get(self.url)

        assert response.data["count"] == 12
        assert len(response.data["results"]) == 10
        assert response.data["next"] is not None

    def test_event_log_unauthenticated(self, api_client):
        """Yetkisiz erişimin engellenmesi testi."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


###### SIGNED UPLOAD URL TESTS ############
@pytest.mark.django_db
class TestSignedUploadURL:
    url = reverse("signed-upload")

    @patch("documents.views.create_client")
    def test_signed_upload_success(self, mock_create_client, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        mock_supabase = MagicMock()
        mock_storage = MagicMock()
        mock_bucket = MagicMock()

        mock_create_client.return_value = mock_supabase
        mock_supabase.storage = mock_storage
        mock_storage.from_.return_value = mock_bucket

        mock_bucket.remove.return_value = None
        mock_bucket.create_signed_upload_url.return_value = {
            "signed_url": "https://supabase.co/signed-url-abc",
            "token": "mock-token-123",
        }

        payload = {
            "file_name": "test dökümanı.pdf",
            "content_type": "application/pdf",
            "file_size": 1024 * 1024,
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"]["path"] == "uploads/test_dokuman.pdf"

    def test_signed_upload_invalid_mime(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        payload = {"file_name": "image.png", "content_type": "image/png"}

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "Only application/pdf is allowed."

    def test_signed_upload_size_limit(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        payload = {
            "file_name": "big_file.pdf",
            "content_type": "application/pdf",
            "file_size": 51 * 1024 * 1024,
        }

        response = api_client.post(self.url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["detail"] == "File size exceeds 50MB limit."

    def test_signed_upload_missing_fields(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        response = api_client.post(self.url, {"file_name": "test.pdf"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "file_name and content_type are required." in response.data["detail"]

    def test_signed_upload_unauthenticated(self, api_client):
        response = api_client.post(self.url, {})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
