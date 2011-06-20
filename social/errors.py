
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
    request = None

    def __init__(self, request):
        self.request = request
        BaseError.__init__(self, "Not Found: %s"%request.path)


#
# One or more parameters that are required are missing
#
class MissingParams(BaseError):
    params = None

    def __init__(self, message, params=None):
        self.params = params
        BaseError.__init__(self, message)


#
# Exceptions will be changed to do the following:
#
# 1. Current operation required authentication
#       Unauthorized(message)
# 2. Current user does not have access to an Entity
#       EntityAccessDenied(message, userId, entityId)
# 3. Current user does not have access to an Item
#       ItemAccessDenied(message, userId, itemId)
# 4. Current user has access/autorization but is not
#    permitted to perform the action (eg: in admin tasks)
#       PermissionDenied(message, userId, url)
# 5. User uploaded a file of unknown format
#       InvalidFileFormat(message)
# 6. User uploaded a file that exceeds the maximum permitted size
#       InvalidFileSize(message)
# 7. The requested item does not exist or isn't of the right type
#       InvalidItem(message, userId, givenItemId)
# 8. The requested entity does not exist or isn't of the right type
#       InvalidEntity(message, uesrId, givenEntityId)
# 9. The requested tag does not exist
#       InvalidTag(message, userId, givenTagId)
# 10. Required parameters are missing
#       MissingParams(message)
#











#
# Used in messaging.
#
class AccessDenied(BaseError):
    pass


#
# User trying to signup
# Request the user to signout before trying to signup.
#
class AlreadySignedIn(BaseError):
    pass


#
# Used when an invalid file is uploaded by admin
# to add users.
#
class InvalidData(BaseError):
    pass


#
# EntityId passed in params does not exist or isn't of
# the requested type.
#
class InvalidEntity(BaseError):
    pass


#
# ItemId passed in params does not exist or isn't of
# the requested type.
#
class InvalidItem(BaseError):
    pass


#
# The user trying to register already exists
# or an invalid signup token is being used to register.
#
class InvalidRegistration(BaseError):
    pass


#
# The requested operation cannot be performed
# either due to insufficient privileges or because
# the operation is not meant to be called that way
#
class InvalidRequest(BaseError):
    pass


#
# TagId passed in params does not exist
#
class InvalidTag(BaseError):
    pass


#
# The uploaded file is larger than the maximum allowed size
#
class InvalidFileSize(BaseError):
    pass


#
# User does not have access to the entity
# Will be masked as InvalidEntity when reporting error to the user
#
class NoAccessToEntity(BaseError):
    pass


#
# User does not have access to the item
# Will be masked as InvalidItem when reporting error to the user
#
class NoAccessToItem(BaseError):
    pass


#
#
#
class PasswordsNoMatch(BaseError):
    pass

#
#
#
class PendingRequest(BaseError):
    pass

#
#
#
class TooManyParams(BaseError):
    pass


#
# Authentication is required to perform the action
#
class Unauthorized(BaseError):
    pass


#
# Uploaded file is not a support format
# Eg: Images for avatars etc;
#
class UnknownFileFormat(BaseError):
    pass


#
# The user was banned from the group and cannot join it.
#
class UserBanned(BaseError):
    pass

