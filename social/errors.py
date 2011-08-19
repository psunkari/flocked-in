
from twisted.python     import log
from social             import _

#
# Base for all exceptions in social
#
class BaseError(Exception):
    _message = None
    _errcode = 500

    def __init__(self, message='', errcode=500):
        self._message = message
        self._errcode = errcode

    def __str__(self):
        return self._message

    def _get_message(self):
        return self._message
    message = property(_get_message)

    def _get_errcode(self):
        return self._errcode
    errcode = property(_get_errcode)

    def errorData(self):
        return ("<p>%s<p>"%self.message, self.errcode, self.message)

    def logError(self):
        log.msg(self.message)


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
        BaseError.__init__(self, message, 403)


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
        BaseError.__init__(self, _("I really tried but couldn't find the resource here!"), 404)


#
# One or more parameters that are required are missing
#
class MissingParams(BaseError):
    params = None

    def __init__(self, params=None):
        self.params = params
        message = _("One or more required parameters are missing")
        BaseError.__init__(self, message, 418)  # XXX: No suitable error code

    def errorData(self):
        message = self.message
        params = ", ".join(self.params)
        return ("<p>%s</p><p><b>%s</b></p>"%(message, params), self.errcode,
                "%(message)s: %(params)s" % locals())


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
        BaseError.__init__(self, message, 404)


#
# Access to entity is denied
#
class EntityAccessDenied(BaseError):
    entityId = None

    def __init__(self, entityType, entityId):
        self.entityId = entityId
        message = _("The requested %s does not exist") % _(entityType)
        BaseError.__init__(self, message, 404)

#
# Access to File is denied
#
class AttachmentAccessDenied(BaseError):
    attachmentId = None
    convId = None
    version = None

    def __init__(self, convId, attachmentId, version):
        self.attachmentId = attachmentId
        self.convId = convId
        self.version = version
        message = _("The requested file does not exist")
        BaseError.__init__(self, message, 404)

#
# Access to File is denied
#
class MessageAccessDenied(BaseError):
    convId = None
    def __init__(self, convId):
        self.convId = convId
        message = _("The requested message does not exist")
        BaseError.__init__(self, message, 404)


#
# Invalid itemId was given
#
class InvalidItem(BaseError):
    itemId = None

    def __init__(self, itemType, itemId):
        self.itemId = itemId
        message = _("The requested %s does not exist") % _(itemType)
        BaseError.__init__(self, message, 404)


#
# Invalid entityId was given
#
class InvalidEntity(BaseError):
    entityId = None

    def __init__(self, entityType, entityId):
        self.entityId = entityId
        message = _("The requested %s does not exist") % _(entityType)
        BaseError.__init__(self, message, 404)


#
# Invalid tagId was given
#
class InvalidTag(BaseError):
    tagId = None

    def __init__(self, tagId):
        self.tagId = tagId
        message = _("The requested tag does not exist")
        BaseError.__init__(self, message, 404)

#
# Invalid message was given
#
class InvalidMessage(BaseError):
    convId = None

    def __init__(self, convId):
        self.convId = convId
        message = _("The requested tag does not exist")
        BaseError.__init__(self, message, 404)

#
# Invalid message-attachment was given
#
class InvalidAttachment(BaseError):
    attachmentId = None
    convId = None
    version = None

    def __init__(self, convId, attachmentId, version):
        self.attachmentId = attachmentId
        self.convId = convId
        self.version = version
        message = _("The requested file does not exist")
        BaseError.__init__(self, message, 404)

class InvalidGroupName(BaseError):
    name = None
    def __init__(self, name):
        self.name = name
        message = _("Group '%s' already exists")%(name)
        BaseError.__init__(self, message, 418)
