from twisted.web        import server
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, utils, base
from social.auth        import IAuthInfo
from social.item        import ItemResource

class EventResource(base.BaseResource):
    isLeaf=True
    itemType = "event"

    @defer.inlineCallbacks
    def _eventResponse(self, request):

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

    @defer.inlineCallbacks
    def _post(self, request):
        yield self._eventResponse(request)
        ir = ItemResource(self._ajax)
        yield ir.renderItem(request, False)

    def render_POST(self, request):
        def success(response):
            request.finish()
        def failure(err):
            log.msg(err)
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'post':
            d = self._post(request)
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET
