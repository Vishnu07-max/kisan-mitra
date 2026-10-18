import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from apps.farms.models import Farm

from .inference import ModelNotAvailable
from .models import DiseaseAssessment

PREDICT = "/api/v1/disease/predict/"
LIST = "/api/v1/disease/assessments/"

TOP = {
    "class_id": 3, "label": "Tomato___Late Blight", "crop": "Tomato",
    "condition": "Late Blight", "is_healthy": False, "confidence": 0.97,
}
OK_RESULT = {
    "status": "ok", "reason": None, "outcome": "disease_possible", "experimental": False,
    "max_confidence": 0.97, "model_version": "v-test", "inference_ms": 12.5,
    "top_prediction": TOP, "top_k": [TOP],
    "supported_crops": ["Tomato", "Wheat"], "experimental_crops": ["Wheat"],
}
NO_MATCH_RESULT = {
    "status": "no_match", "reason": "low_confidence", "max_confidence": 0.41,
    "model_version": "v-test", "inference_ms": 11.0,
    "supported_crops": ["Tomato", "Wheat"], "experimental_crops": ["Wheat"],
}


def jpeg_bytes(size=(200, 160), exif=False):
    img = Image.new("RGB", size, (40, 120, 40))
    buf = io.BytesIO()
    if exif:
        tags = Image.Exif()
        tags[0x010F] = "TestCamera"
        img.save(buf, "JPEG", exif=tags)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


class ApiBase(APITestCase):
    def setUp(self):
        cache.clear()
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        patcher = override_settings(MEDIA_ROOT=media)
        patcher.enable()
        self.addCleanup(patcher.disable)
        self.alice = User.objects.create_user("alice", password="StrongPass#2026")
        self.bob = User.objects.create_user("bob", password="StrongPass#2026")
        self.client.force_authenticate(user=self.alice)

    def upload(self, data=None, name="leaf.jpg", ctype="image/jpeg", result=None, side_effect=None, **extra):
        data = jpeg_bytes() if data is None else data
        payload = {"image": SimpleUploadedFile(name, data, content_type=ctype), **extra}
        with patch("apps.disease.views.predict", return_value=result or OK_RESULT, side_effect=side_effect):
            return self.client.post(PREDICT, payload, format="multipart")


class UploadValidationTests(ApiBase):
    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.upload().status_code, 401)

    def test_missing_image_rejected(self):
        res = self.client.post(PREDICT, {}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"]["code"], "validation_error")

    def test_text_file_named_jpg_rejected(self):
        res = self.upload(b"this is not an image at all")
        self.assertEqual(res.status_code, 400)
        self.assertIn("image", res.data["error"]["details"])

    def test_gif_rejected(self):
        buf = io.BytesIO()
        Image.new("P", (100, 100)).save(buf, "GIF")
        self.assertEqual(self.upload(buf.getvalue(), "leaf.gif", "image/gif").status_code, 400)

    def test_tiny_image_rejected(self):
        self.assertEqual(self.upload(jpeg_bytes((20, 20))).status_code, 400)

    def test_oversized_image_rejected(self):
        with override_settings(DISEASE_MAX_UPLOAD_MB=0.0001):
            self.assertEqual(self.upload().status_code, 400)

    def test_model_unavailable_returns_503_and_saves_nothing(self):
        res = self.upload(side_effect=ModelNotAvailable("missing"))
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["error"]["code"], "model_unavailable")
        self.assertEqual(DiseaseAssessment.objects.count(), 0)


class AssessmentTests(ApiBase):
    def test_result_is_saved_and_exif_is_stripped(self):
        res = self.upload(jpeg_bytes(exif=True))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "ok")
        self.assertEqual(res.data["crop"], "Tomato")
        self.assertEqual(res.data["supported_crops"], ["Tomato", "Wheat"])
        assessment = DiseaseAssessment.objects.get(pk=res.data["id"])
        self.assertEqual(assessment.owner, self.alice)
        with Image.open(assessment.image.path) as stored:
            self.assertEqual(len(stored.getexif()), 0)

    def test_no_match_stores_no_label(self):
        res = self.upload(result=NO_MATCH_RESULT)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "no_match")
        self.assertEqual(res.data["crop"], "")
        self.assertEqual(res.data["top_k"], [])

    def test_farm_must_belong_to_the_user(self):
        theirs = Farm.objects.create(owner=self.bob, name="B", state="UP", district="Lucknow")
        self.assertEqual(self.upload(farm_id=str(theirs.id)).status_code, 400)
        mine = Farm.objects.create(owner=self.alice, name="A", state="UP", district="Lucknow")
        res = self.upload(farm_id=str(mine.id))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["farm_id"], mine.id)

    def test_history_is_own_only_newest_first_and_paginated(self):
        first = self.upload().data["id"]
        second = self.upload().data["id"]
        self.client.force_authenticate(user=self.bob)
        self.upload()
        self.client.force_authenticate(user=self.alice)
        res = self.client.get(LIST)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 2)
        self.assertEqual([r["id"] for r in res.data["results"]], [second, first])

    def test_other_users_assessment_is_hidden(self):
        self.client.force_authenticate(user=self.bob)
        pk = self.upload().data["id"]
        self.client.force_authenticate(user=self.alice)
        for url in (f"{LIST}{pk}/", f"{LIST}{pk}/image/"):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.delete(f"{LIST}{pk}/").status_code, 404)
        self.assertTrue(DiseaseAssessment.objects.filter(pk=pk).exists())

    def test_owner_can_fetch_image_and_delete_removes_the_file(self):
        pk = self.upload().data["id"]
        path = Path(DiseaseAssessment.objects.get(pk=pk).image.path)
        self.assertTrue(path.exists())

        res = self.client.get(f"{LIST}{pk}/image/")
        self.assertEqual(res.status_code, 200)
        body = b"".join(res.streaming_content)
        res.close()
        self.assertEqual(res["Content-Type"], "image/jpeg")
        self.assertTrue(body.startswith(b"\xff\xd8"))

        self.assertEqual(self.client.delete(f"{LIST}{pk}/").status_code, 204)
        self.assertFalse(DiseaseAssessment.objects.filter(pk=pk).exists())
        self.assertFalse(path.exists())