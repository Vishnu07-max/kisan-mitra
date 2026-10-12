from django.db import connection
from django.http import JsonResponse


def health(request):
    """Simple check that the API and database are both working."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception:
        db_status = "error"

    return JsonResponse(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "service": "Kisan Mitra API",
            "version": "v1",
            "database": db_status,
        }
    )