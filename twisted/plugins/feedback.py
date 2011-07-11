import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import db, base, utils, errors
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import dump_args, profile


class Feedback(object):
    implements(IPlugin, IItemType)
    itemType = "feedback"
    position = -1
    hasIndex = False

    def shareBlockProvider(self):
        raise Exception("No block provider for feedback")


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("item.mako", "render_feedback", **args)
        else:
            return getBlock("item.mako", "render_feedback", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        conv = args["items"][convId]
        return defer.succeed(set([conv["meta"]["userId"], conv["meta"]["userOrgId"]]))


    def create(self, request):
        raise Exception("Feedback item cannot be created from share block")


    @defer.inlineCallbacks
    def delete(self, itemId):
        log.msg("plugin:delete", itemId)
        yield db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None


feedback = Feedback()
