from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class FarmerProfile(models.Model):
    """Extra details about a farmer. Passwords stay in Django's built-in User."""

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        HINDI = "hi", "Hindi"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ENGLISH
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        validators=[RegexValidator(r"^\+?\d{10,13}$", "Enter a valid phone number.")],
    )
    state = models.CharField(max_length=60, blank=True)
    district = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile of {self.user.username}"