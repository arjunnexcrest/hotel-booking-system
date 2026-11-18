from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Standardizes error responses across all API endpoints.
    """
    response = exception_handler(exc, context)

    if response is not None:
        data = {
            'success': False,
            'status_code': response.status_code,
            'message': 'An error occurred while processing your request.',
            'errors': response.data,
        }

        # Handle simple detail strings
        if isinstance(response.data, dict) and 'detail' in response.data:
            data['message'] = str(response.data['detail'])

        response.data = data

    return response
