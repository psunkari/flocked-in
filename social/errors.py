
#
# Base for all exceptions in social
#
class BaseError(Exception):
    _message = None
    def __init__(self, message=''):
        self._message = message
    def __str__(self):
        return self._message
    def _get_message(self):
        return self._message
    message = property(_get_message)


#
# Requires user to be signed in
#
class Unauthorized(BaseError):
    pass

#
# Current user has access/autorization but is not
# permitted to perform the action (eg: in admin tasks)
#
class PermissionDenied(BaseError):
    userId = None
    taskId = None

    def __init__(self, message='', userId=None, taskId=None):
        self.userId = userId
        self.taskId = taskId
        BaseError.__init__(self, message)


#
# The requested operation cannot be performed
# either due to insufficient privileges or because
# the operation is not meant to be called that way
#
class InvalidRequest(BaseError):
    pass


#
# No such path
#
class NotFoundError(BaseError):
    def __init__(self):
        BaseError.__init__(self, "Not Found")


#
# One or more parameters that are required are missing
#
class MissingParams(BaseError):
    params = None

    def __init__(self, message, params=None):
        self.params = params
        BaseError.__init__(self, message)


#
# A required configuration parameter is missing or is invalid.
#
class ConfigurationError(BaseError):
    pass


#
# Access to item is denied
#
class ItemAccessDenied(BaseError):
    itemId = None
    userId = None

    def __init__(self, message, itemId):
        self.itemId = itemId
        self.userId = userId
        BaseError.__init__(self, message)


#
# Access to entity is denied
#
class EntityAccessDenied(BaseError):
    entityId = None

    def __init__(self, message, entityId):
        self.entityId = itemId
        self.userId = userId
        BaseError.__init__(self, message)


#
# Invalid itemId was given
#
class InvalidItem(BaseError):
    itemId = None

    def __init__(self, message, itemId):
        self.itemId = itemId
        BaseError.__init__(self, message)


#
# Invalid entityId was given
#
class InvalidEntity(BaseError):
    entityId = None

    def __init__(self, message, entityId):
        self.entityId = entityId
        BaseError.__init__(self, message)


#
# Invalid tagId was given
#
class InvalidTag(BaseError):
    tagId = None

    def __init__(self, message, tagId):
        self.tagId = tagId
        BaseError.__init__(self, message)


