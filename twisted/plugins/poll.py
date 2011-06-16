import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import db, utils, base, errors, _
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import profile, dump_args


class PollResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _vote(self, request):
        convId, conv = yield utils.getAccessibleItemId(request,
                                                'id', ['options'], 'poll')
        vote = utils.getRequestArg(request, 'option')
        if not vote or vote not in conv.get("options", {}):
            raise errors.InvalidRequest()

        optionCounts = {}
        myId = request.getSession(IAuthInfo).username

        prevVote = yield db.get_slice(myId, "userVotes", [convId])
        prevVote = prevVote[0].column.value if prevVote else False
        if prevVote == vote:
            yield self._results(request)
            return

        if prevVote:
            yield db.remove(convId, "votes", myId, prevVote)
            prevOptionCount = yield db.get_count(convId, "votes", prevVote)
            optionCounts[prevVote] = str(prevOptionCount)

        yield db.insert(myId, "userVotes", vote, convId)
        yield db.insert(convId, "votes",  '', myId, vote)

        voteCount = yield db.get_count(convId, "votes", vote)
        optionCounts[vote] = str(voteCount)

        yield db.batch_insert(convId, "items", {"counts":optionCounts})
        yield self._results(request)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _results(self, request):
        convId = utils.getRequestArg(request, "id");
        if not convId:
            raise errors.InvalidRequest()

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId, ["meta"])

        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        yield renderScriptBlock(request, "poll.mako", 'poll_results',
                                False, '#poll-contents-%s'%convId, 'set',
                                args=[convId, voted], **data)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _change(self, request):
        convId = utils.getRequestArg(request, "id");
        if not convId:
            raise errors.InvalidRequest()

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId, ["meta"])

        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        yield renderScriptBlock(request, "poll.mako", 'poll_options',
                                False, '#poll-contents-%s'%convId, 'set',
                                args=[convId, voted], **data)

    @defer.inlineCallbacks
    def _listVoters(self, request):
        convId, item = yield utils.getValidItemId(request, "id",
                                                  ["options"], "poll")

        myId = request.getSession(IAuthInfo).username
        myVote = yield db.get_slice(myId, "userVotes", [convId])
        myVote = myVote[0].column.value if myVote else None
        if not myVote:
            raise errors.InvalidRequest();

        option = utils.getRequestArg(request, "option")
        if not option or option not in item.get("options", {}):
            raise errors.MissingParams();

        votes = yield db.get_slice(convId, "votes", [option])
        votes = utils.supercolumnsToDict(votes)
        voters = set()
        if votes:
            for option in votes:
                voters.update(votes[option].keys())

        args = {'entities': {}, 'users': voters}
        args['title'] = _('List of people who voted for "%s"')\
                                                    % item["options"][option]
        if voters:
            people = yield db.multiget_slice(voters, "entities", ["basic"])
            people = utils.multiSuperColumnsToDict(people)
            args['entities'] = people

        yield renderScriptBlock(request, "item.mako", "userListDialog", False,
                            "#poll-users-%s-%s"%(option, convId), "set", **args)


    @profile
    @dump_args
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

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1:
            if request.postpath[0] == 'results':
                d = self._results(request)
            elif request.postpath[0] == 'change':
                d = self._change(request)
            elif request.postpath[0] == 'voters':
                d = self._listVoters(request)

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

    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        templateFile = "poll.mako"
        renderDef = "share_poll"

        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "poll"},
                                handlers={"onload": "(function(obj){$$.publisher.load(obj);$('#share-poll-options').delegate('.input-wrap:last-child','focus',function(event){$(event.target.parentNode).clone().appendTo('#share-poll-options').find('input:text').blur();});})(this);"})


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("poll.mako", "poll_root", **args)
        else:
            return getBlock("poll.mako", "poll_root", args=[convId, isQuoted], **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def fetchData(self, args, convId=None, userId=None, columns=[]):
        convId = convId or args["convId"]
        myId = userId or args.get("myKey", None)

        conv = yield db.get_slice(convId, "items",
                                  ['options', 'counts'].extend(columns))
        if not conv:
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv, True)
        conv.update(args.get("items", {}).get(convId, {}))

        options = conv["options"] if conv.has_key("options") else None
        if not options:
            raise errors.InvalidRequest()

        myVote = yield db.get_slice(myId, "userVotes", [convId])
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

        defer.returnValue(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request):
        myId = request.getSession(IAuthInfo).username

        end = utils.getRequestArg(request, "end")
        start = utils.getRequestArg(request, "start")
        options = utils.getRequestArg(request, "options", True)
        question = utils.getRequestArg(request, "question")
        showResults = utils.getRequestArg(request, "show") or 'True'
        options = [option for option in options if option]

        if not (question and options):
            raise errors.MissingParams()
        if len(options) <2 :
            raise errors.InSufficientParams()

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

        yield db.batch_insert(convId, "items", item)
        defer.returnValue((convId, item))


    @defer.inlineCallbacks
    def delete(self, itemId):
        yield db.get_slice(itemId, "entities")

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
