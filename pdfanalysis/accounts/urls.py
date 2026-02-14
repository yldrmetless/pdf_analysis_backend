from django.urls import path

from .views import LoginAPIView, MyProfileAPIView, RegisterAPIView

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("my-profile/", MyProfileAPIView.as_view(), name="my-profile"),
]
