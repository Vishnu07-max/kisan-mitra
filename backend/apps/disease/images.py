import io

from PIL import Image, ImageOps
from rest_framework.exceptions import ValidationError

ALLOWED_FORMATS = {"JPEG", "PNG"}
MAX_PIXELS = 50_000_000
MIN_SIDE = 64
STORE_MAX_SIDE = 1024


def _fail(message):
    raise ValidationError({"image": [message]})


def read_and_prepare(upload, max_bytes):
    """Validate an uploaded photo. Returns (original_bytes, stored_jpeg_bytes).

    The stored copy is re-encoded, so EXIF metadata (including GPS) is dropped.
    """
    if upload.size > max_bytes:
        _fail(f"The image is larger than {max_bytes / 1048576:g} MB.")
    raw = upload.read()
    try:
        img = Image.open(io.BytesIO(raw))
        fmt, (w, h) = img.format, img.size
    except Exception:
        _fail("The file is not a readable image.")
    if fmt not in ALLOWED_FORMATS:
        _fail("Only JPEG and PNG photos are supported.")
    if w * h > MAX_PIXELS:
        _fail("The image has too many pixels.")
    if min(w, h) < MIN_SIDE:
        _fail("The image is too small. Use a close-up photo of at least 64 pixels on each side.")
    try:
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        _fail("The image file is damaged.")
    img.thumbnail((STORE_MAX_SIDE, STORE_MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)  # re-encoding drops EXIF, including GPS
    return raw, buf.getvalue()