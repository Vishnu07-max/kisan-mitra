from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.farms.models import Farm

from . import inference
from .inference import ModelNotAvailable
from .models import Recommendation

URL = "/api/v1/crops/recommend/"
LIST = "/api/v1/crops/recommendations/"
FULL = {"N": 80, "P": 47, "K": 40, "temperature": 23.7, "humidity": 82, "ph": 6.4, "rainfall": 233}
FAKE = {
    "input_set": "nutrients+ph+climate",
    "suggestions": [{"crop": "rice", "similarity": 0.8, "matches": 7, "checked": 7, "explanation": []}],
    "warnings": [], "model_version": "v-test", "cv_accuracy": 0.99, "chance_level": 0.0455,
    "crops_covered": ["rice"], "not_covered": ["wheat"],
}


class PureFunctionTests(SimpleTestCase):
    def test_input_set_key(self):
        self.assertEqual(inference.input_set_key(FULL), "nutrients+ph+climate")
        self.assertEqual(inference.input_set_key({"ph": 6.5}), "ph")
        self.assertEqual(inference.input_set_key({"N": 1, "P": 2, "K": 3, "ph": 6}), "nutrients+ph")
        self.assertEqual(inference.input_set_key({"N": 1, "P": 2}), "")

    def test_range_warnings(self):
        ranges = {"ph": {"min": 3.5, "max": 9.9}, "N": {"min": 0, "max": 140}}
        out = inference.range_warnings({"ph": 10.5, "N": 50}, ranges)
        self.assertEqual([w["feature"] for w in out], ["ph"])

    def test_explain_positions(self):
        ranges = {"rice": {"ph": {"p10": 5.5, "p50": 6.4, "p90": 7.5}, "N": {"p10": 60, "p50": 80, "p90": 100}}}
        rows = {r["feature"]: r["position"] for r in inference.explain("rice", {"ph": 5.0, "N": 120}, ranges)}
        self.assertEqual(rows, {"N": "above", "ph": "below"})


class ApiBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice", password="StrongPass#2026")
        self.bob = User.objects.create_user("bob", password="StrongPass#2026")
        self.client.force_authenticate(user=self.alice)

    def post(self, payload, **kw):
        with patch("apps.crops.views.recommend", return_value=FAKE, **kw):
            return self.client.post(URL, payload, format="json")


class ValidationTests(ApiBase):
    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.post(FULL).status_code, 401)

    def test_full_and_ph_only_inputs_accepted(self):
        self.assertEqual(self.post(FULL).status_code, 201)
        self.assertEqual(self.post({"ph": 6.5}).status_code, 201)

    def test_partial_nutrient_group_rejected(self):
        res = self.post({"N": 50, "P": 40})
        self.assertEqual(res.status_code, 400)
        self.assertIn("K", res.data["error"]["details"])

    def test_no_inputs_rejected(self):
        self.assertEqual(self.post({}).status_code, 400)

    def test_impossible_values_rejected(self):
        self.assertEqual(self.post({"ph": 15}).status_code, 400)
        self.assertEqual(self.post({"humidity": 120, "temperature": 20, "rainfall": 50}).status_code, 400)

    def test_nan_rejected(self):
        self.assertEqual(self.post({"ph": "nan"}).status_code, 400)

    def test_model_unavailable_returns_503_and_saves_nothing(self):
        with patch("apps.crops.views.recommend", side_effect=ModelNotAvailable("missing")):
            res = self.client.post(URL, FULL, format="json")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(Recommendation.objects.count(), 0)


class OwnershipTests(ApiBase):
    def test_farm_must_belong_to_the_user(self):
        theirs = Farm.objects.create(owner=self.bob, name="B", state="UP", district="Lucknow")
        self.assertEqual(self.post({**FULL, "farm_id": theirs.id}).status_code, 400)
        mine = Farm.objects.create(owner=self.alice, name="A", state="UP", district="Lucknow")
        self.assertEqual(self.post({**FULL, "farm_id": mine.id}).data["farm_id"], mine.id)

    def test_history_is_own_only_newest_first(self):
        first = self.post(FULL).data["id"]
        second = self.post({"ph": 6}).data["id"]
        self.client.force_authenticate(user=self.bob)
        self.post(FULL)
        self.client.force_authenticate(user=self.alice)
        res = self.client.get(LIST)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual([r["id"] for r in res.data["results"]], [second, first])

    def test_other_users_record_is_hidden(self):
        self.client.force_authenticate(user=self.bob)
        pk = self.post(FULL).data["id"]
        self.client.force_authenticate(user=self.alice)
        self.assertEqual(self.client.get(f"{LIST}{pk}/").status_code, 404)
        self.assertEqual(self.client.delete(f"{LIST}{pk}/").status_code, 404)

    def test_owner_can_delete(self):
        pk = self.post(FULL).data["id"]
        self.assertEqual(self.client.delete(f"{LIST}{pk}/").status_code, 204)


MODEL_FILE = Path(settings.CROP_MODEL_DIR) / "model.joblib"
try:
    import sklearn  # noqa: F401

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


@skipUnless(HAS_SKLEARN and MODEL_FILE.exists(), "trained model or scikit-learn not available")
class RealModelTests(SimpleTestCase):
    def test_typical_rice_values_rank_rice_in_top_three(self):
        res = inference.recommend(FULL)
        self.assertIn("rice", [s["crop"] for s in res["suggestions"]])
        self.assertEqual(res["input_set"], "nutrients+ph+climate")
        self.assertNotIn("wheat", res["crops_covered"])
        self.assertIn("wheat", res["not_covered"])

    def test_out_of_range_input_is_flagged(self):
        res = inference.recommend({"ph": 13.0})
        self.assertEqual([w["feature"] for w in res["warnings"]], ["ph"])