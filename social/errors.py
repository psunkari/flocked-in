
#
# Used in messaging.
#
class AccessDenied(Exception):
    pass

#
# User trying to signup
# Request the user to signout before trying to signup.
#
class AlreadySignedIn(Exception):
    pass


#
# Used when an invalid file is uploaded by admin
# to add users.
#
class InvalidData(Exception):
    pass


#
# EntityId passed in params does not exist or isn't of
# the requested type.
#
class InvalidEntity(Exception):
    pass


#
# ItemId passed in params does not exist or isn't of
# the requested type.
#
class InvalidItem(Exception):
    pass


#
# The user trying to register already exists
# or an invalid signup token is being used to register.
#
class InvalidRegistration(Exception):
    pass


#
# The requested operation cannot be performed
# either due to insufficient privileges or because
# the operation is not meant to be called that way
#
class InvalidRequest(Exception):
    pass


#
# TagId passed in params does not exist
#
class InvalidTag(Exception):
    pass


#
#
#
class LargeFile(Exception):
    pass


#
#
#
class MissingData(Exception):
    pass


#
# One or more parameters that are required are missing
#
class MissingParams(Exception):
    pass


#
#
#
class NoAccessToEntity(Exception):
    pass


#
#
#
class NoAccessToItem(Exception):
    pass


#
#
#
class NotAllowed(Exception):
    pass

#
#
#
class NotAuthorized(Exception):
    pass

#
#
#
class PasswordsNoMatch(Exception):
    pass

#
#
#
class PendingRequest(Exception):
    pass

#
#
#
class TooManyParams(Exception):
    pass

#
#
#
class UnAuthoried(Exception):
    pass

#
#
#
class UnAuthorised(Exception):
    pass

#
#
#
class UnAuthorized(Exception):
    pass

#
#
#
class UnknownFileFormat(Exception):
    pass

#
#
#
class UnknownUser(Exception):
    pass

#
#
#
class UnsupportedFileType(Exception):
    pass

#
#
#
class UserBanned(Exception):
    pass

