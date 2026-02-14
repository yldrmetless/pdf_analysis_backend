import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


########### REGISTER TEST ################
@pytest.mark.django_db
class TestRegistration:
    """Kullanıcı kayıt işlemlerini test eden sınıf."""

    register_url = reverse("register")

    def test_register_user_success(self, api_client):
        """Başarılı kayıt senaryosu."""
        payload = {
            "username": "metehan",
            "email": "metehan@example.com",
            "password": "securepassword123",
            "first_name": "Metehan",
            "last_name": "Yildirim",
        }

        response = api_client.post(self.register_url, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["username"] == payload["username"]
        assert response.data["email"] == payload["email"]
        assert "password" not in response.data
        assert User.objects.filter(username=payload["username"]).exists()

    def test_register_user_duplicate_email(self, api_client):
        """Aynı email ile ikinci kayıt hatası testi."""
        User.objects.create_user(
            username="testuser1", email="duplicate@example.com", password="password123"
        )

        payload = {
            "username": "testuser2",
            "email": "duplicate@example.com",
            "password": "password123",
        }

        response = api_client.post(self.register_url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_user_short_password(self, api_client):
        """Kısa şifre (min_length=8) kontrolü."""
        payload = {
            "username": "testuser3",
            "email": "test3@example.com",
            "password": "123",
        }

        response = api_client.post(self.register_url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data


#####################LOGIN TEST#####################


@pytest.fixture
def test_user(db):
    """Giriş testleri için aktif bir kullanıcı oluşturur."""
    return User.objects.create_user(
        username="metehany",
        email="mete@yildirim.com",
        password="password123",
        is_active=True,
    )


@pytest.mark.django_db
class TestLogin:
    def test_login_success_with_username(self, api_client, test_user):
        url = reverse("login")
        payload = {"username_or_email": "metehany", "password": "password123"}

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.data
        assert "refresh_token" in response.data
        assert "expires_time" in response.data

    def test_login_success_with_email(self, api_client, test_user):
        url = reverse("login")
        payload = {"username_or_email": "METE@yildirim.com", "password": "password123"}

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.data

    def test_login_fail_wrong_password(self, api_client, test_user):
        url = reverse("login")
        payload = {"username_or_email": "metehany", "password": "wrongpassword"}

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["detail"] == "The username/email or password is incorrect."

    def test_login_fail_inactive_user(self, api_client, test_user):
        test_user.is_active = False
        test_user.save()

        url = reverse("login")
        payload = {"username_or_email": "metehany", "password": "password123"}

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data["detail"] == "This user is inactive."


######################MY PROFILE TEST#####################
@pytest.mark.django_db
class TestMyProfile:
    url = reverse("my-profile")

    def test_get_profile_success(self, api_client, test_user):
        """Giriş yapmış kullanıcının profil bilgilerini başarıyla alması testi."""
        api_client.force_authenticate(user=test_user)

        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == 200

        results = response.data["results"]
        assert results["username"] == test_user.username
        assert results["email"] == test_user.email
        assert results["first_name"] == test_user.first_name
        assert results["last_name"] == test_user.last_name

        assert "password" not in results

    def test_get_profile_unauthenticated(self, api_client):
        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
