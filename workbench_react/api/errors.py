# workbench/api/errors.py
"""
Custom exceptions and error handling for Workbench sync API
Centralizes all error types and messages
"""

class WorkbenchError(Exception):
    """Base exception for Workbench"""
    pass


class ValidationError(WorkbenchError):
    """Raised when payload validation fails"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class PermissionError(WorkbenchError):
    """Raised when user lacks permission"""
    def __init__(self, action: str, resource: str):
        self.message = f'Permission denied {action} {resource}'
        super().__init__(self.message)


class NotFoundError(WorkbenchError):
    """Raised when resource not found"""
    def __init__(self, resource_type: str, resource_id: str):
        self.message = f'{resource_type} {resource_id} not found'
        super().__init__(self.message)


class OwnershipError(WorkbenchError):
    """Raised when user doesn't own the resource"""
    def __init__(self, resource_type: str, resource_id: str):
        self.message = f'Cannot modify {resource_type} created by other users'
        super().__init__(self.message)


class TransactionError(WorkbenchError):
    """Raised when batch operation fails"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# Error message constants
ERROR_MESSAGES = {
    'MISSING_TYPE_PAGE_ID': 'Missing type or pageId',
    'MISSING_BLOCK_ID_TYPE': 'Block must have id and type',
    'MISSING_BLOCK_ID': 'Block id is required',
    'MISSING_PAGE_TITLE': 'Page title is required',
    'INVALID_JSON': 'Invalid JSON format',
    'PERMISSION_DENIED': 'Permission denied',
    'BATCH_EMPTY': 'Transactions must be non-empty list',
    'UNKNOWN_PRESENCE_ACTION': 'Unknown presence action',
    'INVALID_OPERATION': 'Unknown operation type',
    'SERVER_ERROR': 'Server error',
    'BATCH_FAILED': 'Batch transaction failed',
}
