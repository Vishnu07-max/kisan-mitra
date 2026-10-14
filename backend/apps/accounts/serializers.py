from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import FarmerProfile

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    password = serializers.CharField(write_only=True, min_length=8, max_length=128)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(
        choices=FarmerProfile.Language.choices, default=FarmerProfile.Language.ENGLISH
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate(self, attrs):
        try:
            validate_password(attrs["password"], user=User(username=attrs["username"]))
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            password=validated_data["password"],  # Django hashes it for us
            first_name=validated_data.get("full_name", ""),
        )
        FarmerProfile.objects.create(
            user=user, preferred_language=validated_data["preferred_language"]
        )
        return user


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(
        source="user.first_name", required=False, allow_blank=True, max_length=150
    )

    class Meta:
        model = FarmerProfile
        fields = ["username", "full_name", "preferred_language", "phone", "state", "district"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "first_name" in user_data:
            instance.user.first_name = user_data["first_name"]
            instance.user.save(update_fields=["first_name"])
        return super().update(instance, validated_data)