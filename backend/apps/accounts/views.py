from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import FarmerProfile
from .serializers import ProfileSerializer, RegisterSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": {"id": user.id, "username": user.username},
                "tokens": {"access": str(refresh.access_token), "refresh": str(refresh)},
            },
            status=201,
        )


class LoginView(TokenObtainPairView):
    """Returns {access, refresh}. Rate-limited to slow down password guessing."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LogoutView(APIView):
    """Blacklists the refresh token so it can't be used again."""

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            raise ValidationError({"refresh": ["This field is required."]})
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            raise ValidationError({"refresh": ["Invalid or expired token."]})
        return Response(status=204)


class ProfileView(generics.RetrieveUpdateAPIView):
    """A farmer can only ever see and edit their OWN profile."""

    serializer_class = ProfileSerializer

    def get_object(self):
        profile, _ = FarmerProfile.objects.get_or_create(user=self.request.user)
        return profile