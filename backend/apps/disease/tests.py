import sys
import tempfile
from pathlib import Path
from unittest import skipUnless

import numpy as np
from django.conf import settings
from django.test import SimpleTestCase, override_settings
from PIL import Image

from . import inference

CLASSES = ["Apple___Apple Scab", "Apple___Healthy", "Rice___Brown Spot", "Wheat___Stripe Rust"]
KW = dict(disease_min=0.90, healthy_min=0.95, withheld_crops=("Rice",), experimental_crops=("Wheat",))


def result(probs):
    return inference.build_result(probs, CLASSES, "v-test", **KW)


class BuildResultTests(SimpleTestCase):
    def test_confident_disease_is_answered(self):
        res = result([0.95, 0.02, 0.02, 0.01])
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["outcome"], "disease_possible")
        self.assertEqual(res["top_prediction"]["label"], "Apple___Apple Scab")
        self.assertFalse(res["experimental"])

    def test_below_disease_threshold_is_no_match_without_a_label(self):
        res = result([0.85, 0.05, 0.05, 0.05])
        self.assertEqual(res["status"], "no_match")
        self.assertEqual(res["reason"], "low_confidence")
        self.assertNotIn("top_prediction", res)
        self.assertNotIn("top_k", res)

    def test_healthy_needs_higher_confidence(self):
        self.assertEqual(result([0.02, 0.92, 0.03, 0.03])["status"], "no_match")
        ok = result([0.01, 0.97, 0.01, 0.01])
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["outcome"], "no_disease_detected")

    def test_withheld_crop_is_never_answered(self):
        res = result([0.0, 0.0, 0.99, 0.01])
        self.assertEqual(res["status"], "no_match")
        self.assertEqual(res["reason"], "withheld_class")

    def test_experimental_flag(self):
        self.assertTrue(result([0.0, 0.0, 0.0, 1.0])["experimental"])
    def test_withheld_crops_are_not_listed_in_top_k(self):
        res = result([0.92, 0.0, 0.07, 0.01])
        self.assertEqual(res["status"], "ok")
        self.assertTrue(all(x["crop"] != "Rice" for x in res["top_k"]))

    def test_top_k_sorted_by_confidence(self):
        confs = [t["confidence"] for t in result([0.92, 0.04, 0.02, 0.02])["top_k"]]
        self.assertEqual(confs, sorted(confs, reverse=True))

    def test_crop_and_condition_are_split(self):
        top = result([0.0, 0.0, 0.0, 1.0])["top_prediction"]
        self.assertEqual((top["crop"], top["condition"]), ("Wheat", "Stripe Rust"))


class FailureTests(SimpleTestCase):
    def test_missing_model_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as empty:
            with override_settings(DISEASE_MODEL_DIR=empty):
                with self.assertRaises(inference.ModelNotAvailable):
                    inference.predict(b"anything")

    def test_non_image_bytes_rejected(self):
        with self.assertRaises(inference.InvalidImage):
            inference.preprocess(b"this is not an image", 224)


MODEL_DIR = Path(settings.DISEASE_MODEL_DIR)
ML_DISEASE = Path(settings.BASE_DIR).parent / "ml" / "disease"
try:
    import tensorflow  # noqa: F401

    HAS_TF = True
except ImportError:
    HAS_TF = False


@skipUnless(HAS_TF and ML_DISEASE.exists(), "TensorFlow or the ml folder not available")
class PreprocessParityTests(SimpleTestCase):
    def test_serving_matches_training_pipeline(self):
        """The web app must prepare an upload exactly as the training data was prepared."""
        import tensorflow as tf

        sys.path.insert(0, str(ML_DISEASE))
        from v2_common import process

        rng = np.random.default_rng(0)
        yy, xx = np.mgrid[0:900, 0:1200]
        arr = np.stack([xx / 1200 * 255, yy / 900 * 255, (xx + yy) / 2100 * 255], axis=-1)
        arr = np.clip(arr + rng.normal(0, 8, arr.shape), 0, 255).astype(np.uint8)

        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "big.jpg", Path(tmp) / "std.jpg"
            Image.fromarray(arr).save(src, "JPEG", quality=85)
            _, h = process((str(src), str(dst)))
            self.assertIsNotNone(h)
            trained = tf.image.resize(
                tf.io.decode_jpeg(tf.io.read_file(str(dst)), channels=3), (224, 224), antialias=True
            ).numpy()
            served = inference.preprocess(src.read_bytes(), 224)
        self.assertLess(float(np.abs(trained - served).max()), 1.0)


@skipUnless(HAS_TF and (MODEL_DIR / "model.keras").exists(), "trained model or TensorFlow not available")
class RealModelTests(SimpleTestCase):
    def test_real_model_returns_well_formed_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plain.jpg"
            Image.new("RGB", (300, 200), (40, 120, 40)).save(path)
            res = inference.predict(str(path))
        self.assertIn(res["status"], ("ok", "no_match"))
        self.assertNotIn("Rice", res["supported_crops"])
        self.assertIn("Sugarcane", res["supported_crops"])
        if res["status"] == "ok":
            confs = [t["confidence"] for t in res["top_k"]]
            self.assertEqual(confs, sorted(confs, reverse=True))
        else:
            self.assertNotIn("top_prediction", res)