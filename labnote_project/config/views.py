from django.http import JsonResponse
from django.db import connection

def db_test(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
        return JsonResponse({
            "status": "ok",
            "message": "PostgreSQL 연결 성공",
            "version": version
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        })
