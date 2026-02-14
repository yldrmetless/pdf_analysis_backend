from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from analysis.models import AnalysisJob
from documents.models import Document

User = get_user_model()


@pytest.fixture
def api_client():
    """Testler için API istemcisi sağlar."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Testler için standart bir kullanıcı oluşturur."""
    return User.objects.create_user(
        username="metehany", email="mete@yildirim.com", password="password123"
    )


@pytest.mark.django_db
class TestDocumentFullAnalysis:
    def test_create_full_analysis_success(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)

        doc = Document.objects.create(
            owner=test_user, title="Analysis Doc", file_size=1024, status="READY"
        )

        url = reverse("analysis-full", kwargs={"id": doc.id})

        with patch("analysis.views.run_full_analysis.delay") as mock_task:
            response = api_client.post(url)

            assert response.status_code == status.HTTP_201_CREATED

            job = AnalysisJob.objects.filter(document=doc, job_type="FULL").first()
            assert job is not None
            assert job.status == "PENDING"

            mock_task.assert_called_once_with(job.id)

    def test_create_full_analysis_conflict(self, api_client, test_user):
        """Zaten çalışan bir iş varken (409) hatası testi."""
        api_client.force_authenticate(user=test_user)
        doc = Document.objects.create(owner=test_user, title="Busy", file_size=1024)

        AnalysisJob.objects.create(document=doc, job_type="FULL", status="PROCESSING")

        url = reverse("analysis-full", kwargs={"id": doc.id})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_create_full_analysis_not_found(self, api_client, test_user):
        """Olmayan döküman için 404 testi."""
        api_client.force_authenticate(user=test_user)
        url = reverse("analysis-full", kwargs={"id": 9999})
        response = api_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
