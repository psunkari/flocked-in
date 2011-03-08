import time
import uuid
from zope.interface     import implements

from twisted.python     import log
from twisted.web        import server
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, errors
from social.auth        import IAuthInfo
from social.isocial     import IItem
from social.template    import render, renderScriptBlock, getBlock


class Activity(object):
    implements(IPlugin, IItem)
    itemType = "activity"
    position = 100
    hasIndex = False

    def getRootHTML(self, convId, args):
        return getBlock("item.mako", "renderStatus", args=[convId], **args)


    @defer.inlineCallbacks
    def getRootData(self, args, convId=None):

        convId = convId or args["convId"]
        toFetchUsers = set()
        toFetchGroups = set()

        conv = yield Db.get_slice(convId, "items", ['meta'])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.MissingParams()

        subtype = conv["meta"]["subType"]

        if subtype in ('connection', 'following'):
            toFetchUsers.add(conv["meta"]["target"])

        if subtype  == 'group':
            toFetchGroups.add(conv["meta"]["target"])

        toFetchUsers.add(conv["meta"]["owner"])
        args.setdefault("items", {})[convId] = conv

        defer.returnValue([toFetchUsers, toFetchGroups])


    @defer.inlineCallbacks
    def renderRoot(self, request, convId, args):
        script = args['script']
        landing = not args['ajax']
        toFeed = args['toFeed'] if args.has_key('toFeed') else False
        if script:
            if not toFeed:
                yield renderScriptBlock(request, "item.mako", "conv_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)

    @defer.inlineCallbacks
    def create(self, request):
        raise errors.InvalidRequest()


    @defer.inlineCallbacks
    def post(self, request):
        pass


activity = Activity()
