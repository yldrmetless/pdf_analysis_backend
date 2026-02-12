from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from accounts.serializers import LoginSerializer, MyProfileSerializer, RegisterSerializer
from rest_framework.permissions import IsAuthenticated


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )
        

class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
    
    
    
class MyProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MyProfileSerializer(request.user)

        return Response(
            {
                "status": 200,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )