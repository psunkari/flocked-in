import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base, errors
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
from social.isocial     import IItemType


class EventResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _rsvp(self, request):
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


    def render_POST(self, request):
        def success(response):
            request.finish()
        def failure(err):
            log.msg(err)
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'rsvp':
            d = self._rsvp(request)
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET


#TODO: event Invitations.
#TODO: listing invitations chronologically.
class Event(object):
    implements(IPlugin, IItemType)
    itemType = "event"
    position = 4
    hasIndex = False


    def shareBlockProvider(self):
        return ("event.mako", "share_event")


    def rootHTML(self, convId, args):
        if "convId" in args:
            return getBlock("event.mako", "event_root", **args)
        else:
            return getBlock("event.mako", "event_root", args=[convId], **args)


    @defer.inlineCallbacks
    def fetchData(self, args, convId=None):
        toFetchUsers = set()
        toFetchGroups = set()
        convId = convId or args["convId"]
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

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myResponse", {})[convId] = myResponse

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
        # TODO: handle no_script case


    @defer.inlineCallbacks
    def create(self, request):
        startTime = utils.getRequestArg(request, 'startTime')
        endTime = utils.getRequestArg(request, 'endTime')
        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc')
        location = utils.getRequestArg(request, 'location')

        if not ((title or desc) and startTime):
            raise errors.InvalidRequest()

        convId = utils.getUniqueKey()
        item = utils.createNewItem(request, self.itemType)

        options = dict([('yes', '0'), ('maybe', '0'), ('no', '0')])
        meta = {"startTime": startTime}
        if title:
            meta["title"] = title
        if desc:
            meta["desc"] = desc
        if endTime:
            meta["endTime"] = endTime
        if location:
            meta["location"] = location

        item["meta"].update(meta)
        item["options"] = options

        yield Db.batch_insert(convId, "items", item)
        defer.returnValue((convId, item))


    _ajaxResource = None
    _resource = None
    def getResource(self, isAjax):
        if isAjax:
            if not self._ajaxResource:
                self._ajaxResource = EventResource(True)
            return self._ajaxResource
        else:
            if not self._resource:
                self._resource = EventResource()
            return self._resource


event = Event()
