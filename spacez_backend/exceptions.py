from django.core.exceptions import ObjectDoesNotExist
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    if isinstance(exc, ObjectDoesNotExist):
        return Response({"detail": "Not found.", "errors": {"detail": "Not found."}}, status=404)
    response = exception_handler(exc, context)
    if response is None:
        return response
    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
    elif isinstance(detail, list) and detail:
        message = str(detail[0])
    else:
        message = str(detail)
    response.data = {"detail": message, "errors": detail}
    return response
