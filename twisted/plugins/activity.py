import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, errors
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import dump_args, profile


class Activity(object):
    implements(IPlugin, IItemType)
    itemType = "activity"
    position = -1
    hasIndex = False

    @defer.inlineCallbacks
    def getReason(self, convId, requesters, userId):
        conv = yield Db.get_slice(convId, "items", ["meta"])
        conv = utils.supercolumnsToDict(conv)

        cols = yield Db.multiget_slice(requesters, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(cols)
        foo = requesters[0]
        if conv["meta"]["subType"] == "connection":
            reasonStr = '%s accepted your friend request' \
                            %(utils.userName(foo, entities[foo]))
        elif conv["meta"]["subType"] == "pendingConnection":
            reasonStr = "%s sent a friend request." \
                        "Click <a href='/profile?id=%s'>here </a> to respond" \
                        %(utils.userName(foo, entities[foo]), foo)
        defer.returnValue(reasonStr)

    def shareBlockProvider(self):
        raise errors.InvalidRequest()

    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("item.mako", "render_activity", **args)
        else:
            return getBlock("item.mako", "render_activity", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request):
        raise errors.InvalidRequest()

    @defer.inlineCallbacks
    def delete(self, itemId):
        log.msg("plugin:delete", itemId)
        yield Db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None


activity = Activity()
