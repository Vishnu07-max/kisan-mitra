from rest_framework import exceptions
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        message = "Some fields are invalid."
        details = response.data
    else:
        code = getattr(exc, "default_code", "error")
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        message = str(detail) if detail else "Request failed."
        details = {}

    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response