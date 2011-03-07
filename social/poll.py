from twisted.web        import server
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, utils, base
from social.item        import ItemResource


class PollResource(base.BaseResource):
    isLeaf=True
    itemType = "poll"

    @defer.inlineCallbacks
    def _castVote(self, request):

        convId = utils.getRequestArg(request, 'id')
        vote = utils.getRequestArg(request, 'option')
        myKey = request.getSession(IAuthInfo).username
        optionCounts = {}

        if not vote:
            raise errors.InvalidRequest()

        item = yield Db.get_slice(convId, "items")
        item = utils.supercolumnsToDict(item)

        if not item  :
            raise errors.MissingParams()

        if (item["meta"].has_key("type") and item["meta"]["type"] != "poll"):
            raise errors.InvalidRequest()

        prevVote = yield Db.get_slice(myKey, "userVotes", [convId])
        prevVote = prevVote[0].column.value if prevVote else ''

        if prevVote == vote:
            return

        if prevVote:
            yield Db.remove(convId, "votes", myKey, prevVote)
            prevOptionCount = yield Db.get_count(convId, "votes", prevVote)
            optionCounts[prevVote] = str(prevOptionCount)

        yield Db.insert(myKey, "userVotes", vote, convId)
        yield Db.insert(convId, "votes",  '', myKey, vote)

        voteCount = yield Db.get_count(convId, "votes", vote)
        optionCounts[vote] = str(voteCount)

        yield Db.batch_insert(convId, "items", {"options":optionCounts})

        defer.returnValue(convId)

    @defer.inlineCallbacks
    def _post(self, request):
        yield self._castVote(request)
        #TODO: update just the poll-data block instead of rendering complete item
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
