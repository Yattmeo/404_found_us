"""
Error handling and utilities for API responses
"""
from flask import jsonify
from validators import ValidationError


class APIError(Exception):
    """Base class for API errors"""
    def __init__(self, message, status_code=400, error_type=None, details=None):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type or 'BAD_REQUEST'
        self.details = details or {}
        super().__init__(self.message)


class ValidationAPIError(APIError):
    """Validation error for API responses"""
    def __init__(self, message, validation_errors=None):
        super().__init__(
            message=message,
            status_code=400,
            error_type='VALIDATION_ERROR',
            details={'validation_errors': validation_errors or []}
        )


class NotFoundError(APIError):
    """Resource not found error"""
    def __init__(self, message, resource_type=None):
        super().__init__(
            message=message,
            status_code=404,
            error_type='NOT_FOUND',
            details={'resource_type': resource_type}
        )


class InternalServerError(APIError):
    """Internal server error"""
    def __init__(self, message):
        super().__init__(
            message=message,
            status_code=500,
            error_type='INTERNAL_SERVER_ERROR'
        )


def error_response(error, status_code=None):
    """
    Generate standardized error response
    """
    if isinstance(error, ValidationError):
        return jsonify({
            'success': False,
            'error': 'Validation failed',
            'error_type': error.error_type,
            'details': {
                'row': error.row,
                'column': error.column,
                'message': error.message,
            }
        }), 400
    
    if isinstance(error, APIError):
        return jsonify({
            'success': False,
            'error': error.message,
            'error_type': error.error_type,
            'details': error.details,
        }), error.status_code
    
    # Generic error
    return jsonify({
        'success': False,
        'error': 'An error occurred',
        'error_type': 'UNKNOWN_ERROR',
    }), status_code or 500


def success_response(data, message=None, status_code=200):
    """
    Generate standardized success response
    """
    return jsonify({
        'success': True,
        'message': message,
        'data': data,
    }), status_code


def paginated_response(items, total, page, per_page, message=None):
    """
    Generate paginated response
    """
    return jsonify({
        'success': True,
        'message': message,
        'data': items,
        'pagination': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
        }
    }), 200
