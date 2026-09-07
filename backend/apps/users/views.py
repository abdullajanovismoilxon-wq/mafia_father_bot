from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import UserRegistrationSerializer, UserProfileSerializer, CoAdminSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Register new user account."""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    """Blacklist refresh token to logout user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get and update authenticated user profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CoAdminListCreateView(generics.ListCreateAPIView):
    """List and create co-admins / moderators for the group owner."""
    serializer_class = CoAdminSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        owner = self.request.user.effective_owner
        return User.objects.filter(parent_admin=owner)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        co_admin = serializer.save()
        data = CoAdminSerializer(co_admin).data
        if hasattr(co_admin, '_raw_password'):
            data['raw_password'] = co_admin._raw_password
        return Response(data, status=status.HTTP_201_CREATED)


class CoAdminDeleteView(generics.DestroyAPIView):
    """Remove co-admin from group."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        owner = self.request.user.effective_owner
        return User.objects.filter(parent_admin=owner)
