import time
import uuid
from zope.interface     import implements

from twisted.python     import log
from twisted.web        import server
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, feed, errors
from social.auth        import IAuthInfo
from social.isocial     import IItem
from social.template    import render, renderScriptBlock


class   Status(object):
    implements(IPlugin, IItem)
    itemType = "status"

    @defer.inlineCallbacks
    def getRoot(self, convId, myKey):
        conv = yield Db.get_slice(convId, "items", ['meta'])
        if not conv:
            raise errors.MissingParams()

        conv = utils.supercolumnsToDict(conv)

        users = yield Db.get_slice(myKey, "users", ["basic"])
        users = utils.supercolumnsToDict(users)

        groups = {}
        myLikes = {convId:[]}
        users = {myKey: users}
        convs = [convId]
        items = {convId: conv}
        likeStr = {convId: None}
        responses = {convId: []}
        itemLikes = {convId:{}}

        defer.returnValue({"items":items, "users": users,"groups": groups,
                           "responses": responses, "myLikes": myLikes,
                           "reasonStr": {}, "likeStr": {},
                           "conversations": convs})


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
