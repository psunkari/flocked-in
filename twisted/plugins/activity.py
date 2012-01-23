import time
import uuid

from zope.interface     import implements
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import db, base, utils, errors
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import dump_args, profile, log
from social             import template as t


class Activity(object):
    implements(IPlugin, IItemType)
    itemType = "activity"
    position = -1
    hasIndex = False

    @defer.inlineCallbacks
    def getReason(self, convId, requesters, userId):
        conv = yield db.get_slice(convId, "items", ["meta"])
        conv = utils.supercolumnsToDict(conv)

        cols = yield db.multiget_slice(requesters, "entities", ["basic"])
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
        raise Exception("No block provider for activity")

    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("item.mako", "render_activity", **args)
        else:
            return t.getBlock("item.mako", "render_activity", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    def create(self, request):
        raise Exception("Activity item cannot be created from share block")

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None


activity = Activity()
