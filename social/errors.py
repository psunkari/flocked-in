
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
# One or more parameters that are required are missing
#
class MissingParams(BaseError):
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

