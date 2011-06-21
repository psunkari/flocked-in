
from twisted.python     import log
from social             import _

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

    def errorData(self):
        return ("<p>%s<p>"%self.message, 500, self.message)

    def logError(self):
        log.msg(self)


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
    taskId = None

    def __init__(self, message='', taskId=None):
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
        BaseError.__init__(self, _("I really tried but couldn't find the resource here!"))


#
# One or more parameters that are required are missing
#
class MissingParams(BaseError):
    params = None

    def __init__(self, params=None):
        self.params = params
        message = _("One or more required parameters are missing")
        BaseError.__init__(self, message)

    def errorData(self):
        message = self.message
        params = ", ".join(self.params)
        return ("<p>%s</p><p><b>%s</b></p>"%(message, params), 500,
                "%(message)s:%(params)s" % locals())


#
# A required configuration parameter is missing or is invalid.
# Intentionally derived from Exception to hide error message from the user.
#
class ConfigurationError(Exception):
    pass


#
# Access to item is denied
#
class ItemAccessDenied(BaseError):
    itemId = None

    def __init__(self, itemType, itemId):
        self.itemId = itemId
        message = _("The requested %s does not exist") % _(itemType)
        BaseError.__init__(self, message)


#
# Access to entity is denied
#
class EntityAccessDenied(BaseError):
    entityId = None

    def __init__(self, entityType, entityId):
        self.entityId = entityId
        message = _("The requested %s does not exist") % _(entityType)
        BaseError.__init__(self, message)


#
# Invalid itemId was given
#
class InvalidItem(BaseError):
    itemId = None

    def __init__(self, itemType, itemId):
        self.itemId = itemId
        message = _("The requested %s does not exist") % _(itemType)
        BaseError.__init__(self, message)


#
# Invalid entityId was given
#
class InvalidEntity(BaseError):
    entityId = None

    def __init__(self, entityType, entityId):
        self.entityId = entityId
        message = _("The requested %s does not exist") % _(entityType)
        BaseError.__init__(self, message)


#
# Invalid tagId was given
#
class InvalidTag(BaseError):
    tagId = None

    def __init__(self, tagId):
        self.tagId = tagId
        message = _("The requested tag does not exist")
        BaseError.__init__(self, message)


