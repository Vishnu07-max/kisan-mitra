from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APITestCase

PASSWORD = "StrongPass#2026"


class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset rate-limit counters between tests

    def register(self, username="farmer1", password=PASSWORD):
        return self.client.post(
            "/api/v1/auth/register/",
            {
                "username": username,
                "password": password,
                "full_name": "Ram Kumar",
                "preferred_language": "hi",
            },
            format="json",
        )

    def login(self, username="farmer1", password=PASSWORD):
        return self.client.post(
            "/api/v1/auth/login/", {"username": username, "password": password}, format="json"
        )

    def test_register_creates_user_profile_and_tokens(self):
        res = self.register()
        self.assertEqual(res.status_code, 201)
        self.assertIn("access", res.data["tokens"])
        user = User.objects.get(username="farmer1")
        self.assertEqual(user.profile.preferred_language, "hi")
        self.assertNotEqual(user.password, PASSWORD)  # stored hashed, never plain

    def test_register_rejects_weak_password(self):
        res = self.register(password="12345678")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"]["code"], "validation_error")

    def test_register_rejects_duplicate_username(self):
        self.register()
        res = self.register(username="FARMER1")
        self.assertEqual(res.status_code, 400)

    def test_login_success(self):
        self.register()
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_login_wrong_password(self):
        self.register()
        res = self.login(password="WrongPass#999")
        self.assertEqual(res.status_code, 401)
        self.assertIn("error", res.data)

    def test_profile_requires_authentication(self):
        res = self.client.get("/api/v1/profile/")
        self.assertEqual(res.status_code, 401)

    def test_profile_get_and_update(self):
        self.register()
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        res = self.client.patch(
            "/api/v1/profile/",
            {"state": "Uttar Pradesh", "district": "Lucknow", "phone": "9876543210"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["district"], "Lucknow")

        res = self.client.get("/api/v1/profile/")
        self.assertEqual(res.data["username"], "farmer1")

    def test_profile_rejects_invalid_phone(self):
        self.register()
        access = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.patch("/api/v1/profile/", {"phone": "abc"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_logout_blocks_refresh_token(self):
        self.register()
        tokens = self.login().data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        res = self.client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 204)

        res = self.client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 401)