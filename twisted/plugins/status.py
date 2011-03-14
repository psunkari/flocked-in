import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, errors
from social.auth        import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock


class Status(object):
    implements(IPlugin, IItemType)
    itemType = "status"
    position = 1
    hasIndex = True

    def shareBlockProvider(self):
        return ("feed.mako", "share_status")

    def rootHTML(self, convId, args):

        if "convId" in args:
            return getBlock("item.mako", "renderStatus", **args)
        else:
            return getBlock("item.mako", "renderStatus", args=[convId], **args)


    @defer.inlineCallbacks
    def fetchData(self, args, convId=None):

        convId = convId or args["convId"]
        toFetchUsers = set()
        toFetchGroups = set()

        conv = yield Db.get_slice(convId, "items", ['meta'])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.MissingParams()

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
            else:
                if 'convId' in args:
                    del args['convId']
                yield renderScriptBlock(request, "item.mako", "item_layout",
                                        landing, "#user-feed", "prepend",
                                        args=[convId, True], **args)
                args['convId'] = convId


    @defer.inlineCallbacks
    def create(self, request):

        myKey = request.getSession(IAuthInfo).username
        target = utils.getRequestArg(request, "target")
        acl = utils.getRequestArg(request, "acl")
        comment = utils.getRequestArg(request, "comment")

        if not comment:
            raise errors.MissingParams()

        convId = utils.getUniqueKey()
        itemType = self.itemType
        timeuuid = uuid.uuid1().bytes

        meta = {}
        meta["acl"] = acl
        meta["type"] = itemType
        meta["uuid"] = timeuuid
        meta["owner"] = myKey
        meta["comment"] = comment
        meta["timestamp"] = "%s" % int(time.time())
        if target:
            meta["target"] = target

        followers = {}
        followers[myKey] = ''

        yield Db.batch_insert(convId, "items", {'meta': meta,
                                                 'followers':followers})
        defer.returnValue([convId, timeuuid, acl])


    @defer.inlineCallbacks
    def post(self, request):
        pass


status = Status()
