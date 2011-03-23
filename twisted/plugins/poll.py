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


class PollResource(base.BaseResource):
    isLeaf = True
    
    @defer.inlineCallbacks
    def _vote(self, request):
        convId = utils.getRequestArg(request, 'id')
        vote = utils.getRequestArg(request, 'option')
        myKey = request.getSession(IAuthInfo).username
        optionCounts = {}

        if not vote:
            raise errors.InvalidRequest()

        item = yield Db.get_slice(convId, "items")
        item = utils.supercolumnsToDict(item)

        if not item:
            raise errors.MissingParams()

        if (item["meta"].has_key("type") and item["meta"]["type"] != "poll"):
            raise errors.InvalidRequest()

        prevVote = yield Db.get_slice(myKey, "userVotes", [convId])
        prevVote = prevVote[0].column.value if prevVote else False

        if prevVote == vote:
            yield self._results(request)
            return

        if prevVote:
            yield Db.remove(convId, "votes", myKey, prevVote)
            prevOptionCount = yield Db.get_count(convId, "votes", prevVote)
            optionCounts[prevVote] = str(prevOptionCount)

        yield Db.insert(myKey, "userVotes", vote, convId)
        yield Db.insert(convId, "votes",  '', myKey, vote)

        voteCount = yield Db.get_count(convId, "votes", vote)
        optionCounts[vote] = str(voteCount)

        yield Db.batch_insert(convId, "items", {"counts":optionCounts})
        yield self._results(request)

    @defer.inlineCallbacks
    def _results(self, request):
        convId = utils.getRequestArg(request, "id");
        if not convId:
            raise errors.InvalidRequest()

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId)
        
        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        yield renderScriptBlock(request, "poll.mako", 'poll_results',
                                False, '#conv-root-%s'%convId, 'set',
                                args=[convId, voted], **data)

    @defer.inlineCallbacks
    def _change(self, request):
        convId = utils.getRequestArg(request, "id");
        if not convId:
            raise errors.InvalidRequest()

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId)
        
        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        yield renderScriptBlock(request, "poll.mako", 'poll_options',
                                False, '#conv-root-%s'%convId, 'set',
                                args=[convId, voted], **data)

    def render_POST(self, request):
        def success(response):
            request.finish()
        def failure(err):
            log.msg(err)
            request.setResponseCode(500)
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'vote':
            d = self._vote(request)
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1:
            if request.postpath[0] == 'results':
                d = self._results(request)
            elif request.postpath[0] == 'change':
                d = self._change(request)

        if d:
            def success(response):
                request.finish()
            def failure(err):
                log.msg(err)
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(success, failure)
            return server.NOT_DONE_YET
        else:
            pass # XXX: 404 error


class Poll(object):
    implements(IPlugin, IItemType)
    itemType = "poll"
    position = 5
    hasIndex = False

    def shareBlockProvider(self):
        return ("poll.mako", "share_poll")

    def rootHTML(self, convId, args):
        if "convId" in args:
            return getBlock("poll.mako", "poll_root", **args)
        else:
            return getBlock("poll.mako", "poll_root", args=[convId], **args)

    @defer.inlineCallbacks
    def fetchData(self, args, convId=None, userId=None):
        toFetchEntities = set()
        convId = convId or args["convId"]
        myKey = userId or args.get("myKey", None)

        conv = yield Db.get_slice(convId, "items", ["meta", 'options', 'counts'])
        if not len(conv):
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv, True)

        options = conv["options"] if conv.has_key("options") else None
        if not options:
            raise errors.InvalidRequest()

        toFetchEntities.add(conv["meta"]["owner"])

        myVote = yield Db.get_slice(myKey, "userVotes", [convId])
        myVote = myVote[0].column.value if myVote else None

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)
        showResults = conv['meta'].get('showResults', 'True') == True

        if not showResults:
            # FIX: endTime is String. convert to time
            if not endTime or time.gmtime() > endTime:
                showResults = "True"

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myVotes", {})[convId] = myVote
        args.setdefault("showResults", {})[convId] = showResults

        defer.returnValue(toFetchEntities)

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
        myKey = request.getSession(IAuthInfo).username

        end = utils.getRequestArg(request, "end")
        start = utils.getRequestArg(request, "start")
        options = request.args.get("options", None)
        question = utils.getRequestArg(request, "question")
        showResults = utils.getRequestArg(request, "show") or 'True'

        if not (question and options):
            raise errors.InvalidRequest()

        convId = utils.getUniqueKey()
        item = utils.createNewItem(request, self.itemType)

        options = dict([('%02d'%(x), options[x]) for x in range(len(options))])
        meta = {"question": question, "showResults": showResults}
        if start:
            meta["start"] = start
        if end:
            meta["end"] = end

        item["options"] = options
        item["meta"].update(meta)

        yield Db.batch_insert(convId, "items", item)
        defer.returnValue((convId, item))

    _ajaxResource = None
    _resource = None
    def getResource(self, isAjax):
        if isAjax:
            if not self._ajaxResource:
                self._ajaxResource = PollResource(True)
            return self._ajaxResource
        else:
            if not self._resource:
                self._resource = PollResource()
            return self._resource


poll = Poll()
