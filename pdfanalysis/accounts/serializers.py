from rest_framework import serializers
from accounts.models import User
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "first_name", "last_name")

    def validate_email(self, value: str):
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu e-posta zaten kullanılıyor.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        ident = attrs["username_or_email"].strip()
        password = attrs["password"]

        user = (
            User.objects.filter(username__iexact=ident).first()
            or User.objects.filter(email__iexact=ident).first()
        )
        if not user or not user.check_password(password):
            raise AuthenticationFailed("Kullanıcı adı/e-posta veya şifre hatalı.")
        if not user.is_active:
            raise AuthenticationFailed("Bu kullanıcı pasif.")

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        expires_minutes = int(
            settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds() // 60
        )

        return {
            "access_token": str(access),
            "refresh_token": str(refresh),
            "expires_time": expires_minutes,
        }
        

class MyProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")