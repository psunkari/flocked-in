import time
import uuid
import traceback
from hashlib            import md5

from zope.interface     import Attribute, Interface, implements
from twisted.plugin     import IPlugin
from twisted.web        import server
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, utils, base
from social.template    import renderScriptBlock, render, getBlock
from social.auth        import IAuthInfo
from social.isocial     import IItem
from social             import errors


class Event(object):
    implements(IPlugin, IItem)
    itemType = "event"
    position = 4
    hasIndex = False
    #TODO: event Invitations.
    #TODO: listing invitations chronologically.

    def getRootHTML(self, convId, args):
        return getBlock("item.mako", "event_root", args=[convId], **args)


    @defer.inlineCallbacks
    def getRootData(self, args):

        toFetchUsers = set()
        toFetchGroups = set()
        convId = args["convId"]
        myKey = args["myKey"]

        conv = yield Db.get_slice(convId, "items", ["meta", "options"])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.InvalidRequest()

        toFetchUsers.add(conv["meta"]["owner"])

        myResponse = yield Db.get_slice(myKey, "userEvents", [convId])
        myResponse = myResponse[0].column.value if myResponse else ''

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)

        items = {convId: conv}
        data = {"items": items, "myResponse": myResponse}
        defer.returnValue([data, toFetchUsers, toFetchGroups])


    @defer.inlineCallbacks
    def renderRoot(self, request, convId, args):

        script = args['script']
        landing = not args['ajax']
        toFeed = args['toFeed'] if args.has_key('toFeed') else False
        if script:
            if not toFeed:
                yield renderScriptBlock(request, "item.mako", "event_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)
            else:
                if 'convId' in args:
                    del args['convId']
                yield renderScriptBlock(request, "item.mako", "item_layout",
                                        landing, "#user-feed", "prepend",
                                        args=[convId, True], **args)
                args['convId'] = convId
        # TODO: handle no_script case


    @defer.inlineCallbacks
    def create(self, request):

        myKey = request.getSession(IAuthInfo).username

        acl = utils.getRequestArg(request, 'acl')
        startTime = utils.getRequestArg(request, 'startTime')
        endTime = utils.getRequestArg(request, 'endTime')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')

        if not ((title or desc) and startTime):
            raise errors.InvalidRequest()

        convId = utils.getUniqueKey()
        itemType = self.itemType
        timeuuid = uuid.uuid1().bytes

        meta = {}
        meta["acl"] = acl
        meta["type"] = itemType
        meta["uuid"] = timeuuid
        meta["owner"] = myKey
        # FIX: convert to gmt time
        meta["startTime"] = startTime
        meta["timestamp"] = "%s" % int(time.time())
        if title:
            meta["title"] = title
        if desc:
            meta["desc"] = desc
        if endTime:
            meta["endTime"] = endTime
        if location:
            meta["location"] = location

        followers = {}
        followers[myKey] = ''
        options = dict([('yes', '0'), ('maybe', '0'), ('no', '0')])

        yield Db.batch_insert(convId, "items", {'meta':meta,
                                                'options': options,
                                                'followers':followers})

        defer.returnValue([convId, timeuuid, acl])


    @defer.inlineCallbacks
    def post(self, request):

        convId = utils.getRequestArg(request, 'id')
        response = utils.getRequestArg(request, 'response')
        myKey = request.getSession(IAuthInfo).username
        optionCounts = {}

        if not response or response not in ('yes', 'maybe', 'no'):
            raise errors.InvalidRequest()

        item = yield Db.get_slice(convId, "items")
        item = utils.supercolumnsToDict(item)

        if not item  :
            raise errors.MissingParams()

        if (item["meta"].has_key("type") and item["meta"]["type"] != self.itemType):
            raise errors.InvalidRequest()

        prevResponse = yield Db.get_slice(myKey, "userEvents", [convId])
        prevResponse = prevResponse[0].column.value if prevResponse else ''

        if prevResponse == response:
            return

        if prevResponse:
            yield Db.remove(convId, "events", myKey, prevResponse)
            prevOptionCount = yield Db.get_count(convId, "events", prevResponse)
            optionCounts[prevResponse] = str(prevOptionCount)

        yield Db.insert(myKey, "userEvents", response, convId)
        yield Db.insert(convId, "events",  '', myKey, response)

        responseCount = yield Db.get_count(convId, "events", response)
        optionCounts[response] = str(responseCount)

        yield Db.batch_insert(convId, "items", {"options":optionCounts})


event = Event()
