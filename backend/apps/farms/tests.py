from django.contrib.auth.models import User
from rest_framework.test import APITestCase

from .models import Farm

FARM = {
    "name": "North Field",
    "state": "Uttar Pradesh",
    "district": "Lucknow",
    "soil_type": "loamy",
    "irrigation_type": "tubewell",
    "area_acres": "2.50",
}


class FarmTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="StrongPass#2026")
        self.bob = User.objects.create_user("bob", password="StrongPass#2026")

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def create_farm(self, user, **overrides):
        self.as_user(user)
        return self.client.post("/api/v1/farms/", {**FARM, **overrides}, format="json")

    # ---- basic behavior ----
    def test_unauthenticated_access_is_rejected(self):
        self.assertEqual(self.client.get("/api/v1/farms/").status_code, 401)

    def test_create_farm_sets_owner_from_login_not_from_request(self):
        res = self.create_farm(self.alice, owner=self.bob.id)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Farm.objects.get(pk=res.data["id"]).owner, self.alice)

    def test_duplicate_farm_name_rejected_for_same_owner(self):
        self.create_farm(self.alice)
        res = self.create_farm(self.alice, name="north field")
        self.assertEqual(res.status_code, 400)

    def test_same_farm_name_allowed_for_different_owners(self):
        self.create_farm(self.alice)
        res = self.create_farm(self.bob)
        self.assertEqual(res.status_code, 201)

    # ---- validation ----
    def test_invalid_latitude_rejected(self):
        res = self.create_farm(self.alice, latitude="95", longitude="80")
        self.assertEqual(res.status_code, 400)

    def test_latitude_without_longitude_rejected(self):
        res = self.create_farm(self.alice, latitude="26.85")
        self.assertEqual(res.status_code, 400)

    def test_valid_coordinates_accepted(self):
        res = self.create_farm(self.alice, latitude="26.846700", longitude="80.946200")
        self.assertEqual(res.status_code, 201)

    # ---- ownership: the important ones ----
    def test_farmer_sees_only_own_farms(self):
        self.create_farm(self.alice)
        self.as_user(self.bob)
        res = self.client.get("/api/v1/farms/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_farmer_cannot_read_edit_or_delete_another_farmers_farm(self):
        farm_id = self.create_farm(self.alice).data["id"]
        self.as_user(self.bob)
        url = f"/api/v1/farms/{farm_id}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, {"name": "Hacked"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(Farm.objects.filter(pk=farm_id).exists())

    def test_owner_can_update_and_delete(self):
        farm_id = self.create_farm(self.alice).data["id"]
        url = f"/api/v1/farms/{farm_id}/"
        res = self.client.patch(url, {"district": "Kanpur"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["district"], "Kanpur")
        self.assertEqual(self.client.delete(url).status_code, 204)


class CropRecordTests(APITestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="StrongPass#2026")
        self.bob = User.objects.create_user("bob", password="StrongPass#2026")
        self.client.force_authenticate(user=self.alice)
        self.farm_id = self.client.post("/api/v1/farms/", FARM, format="json").data["id"]
        self.url = f"/api/v1/farms/{self.farm_id}/crops/"

    def test_create_and_list_crop_record(self):
        res = self.client.post(
            self.url,
            {"crop_name": "Wheat", "season": "rabi", "sowing_date": "2026-11-10"},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(self.client.get(self.url).data), 1)

    def test_harvest_before_sowing_rejected(self):
        res = self.client.post(
            self.url,
            {
                "crop_name": "Wheat", "season": "rabi",
                "sowing_date": "2026-11-10", "expected_harvest_date": "2026-10-01",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_invalid_season_rejected(self):
        res = self.client.post(self.url, {"crop_name": "Wheat", "season": "monsoon"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_other_farmer_cannot_list_or_add_crops(self):
        self.client.post(self.url, {"crop_name": "Wheat", "season": "rabi"}, format="json")
        self.client.force_authenticate(user=self.bob)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        res = self.client.post(self.url, {"crop_name": "Rice", "season": "kharif"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_other_farmer_cannot_touch_a_crop_record(self):
        crop_id = self.client.post(
            self.url, {"crop_name": "Wheat", "season": "rabi"}, format="json"
        ).data["id"]
        self.client.force_authenticate(user=self.bob)
        detail = f"{self.url}{crop_id}/"
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertEqual(self.client.delete(detail).status_code, 404)