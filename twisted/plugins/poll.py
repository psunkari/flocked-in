import time
import uuid
from ordereddict        import OrderedDict

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.web        import server

from social             import db, constants, utils, base, errors, _
from social             import template as t
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import profile, dump_args, log


class PollResource(base.BaseResource):
    isLeaf = True
    _templates = ['poll.mako', 'item.mako']

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _vote(self, request):
        convId, conv = yield utils.getValidItemId(request, 'id', 'poll', ['options'])
        vote = utils.getRequestArg(request, 'option')
        if not vote or vote not in conv.get("options", {}):
            raise errors.MissingParams(["Option"])

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
        convId, conv = yield utils.getValidItemId(request, "id", "poll");

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId, ["meta"])

        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        t.renderScriptBlock(request, "poll.mako", 'poll_results',
                            False, '#poll-contents-%s'%convId, 'set',
                            args=[convId, voted], **data)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _change(self, request):
        convId, conv = yield utils.getValidItemId(request, "id", "poll");

        data = {}
        userId = request.getSession(IAuthInfo).username
        yield poll.fetchData(data, convId, userId, ["meta"])

        myVotes = data["myVotes"]
        voted = myVotes[convId] if (convId in myVotes and myVotes[convId])\
                                else False

        t.renderScriptBlock(request, "poll.mako", 'poll_options',
                            False, '#poll-contents-%s'%convId, 'set',
                            args=[convId, voted], **data)

    @defer.inlineCallbacks
    def _listVoters(self, request):
        convId, item = yield utils.getValidItemId(request, "id", "poll", ["options"])

        option = utils.getRequestArg(request, "option")
        if not option or option not in item.get("options", {}):
            raise errors.MissingParams([_('Option')]);

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

        t.renderScriptBlock(request, "item.mako", "userListDialog", False,
                            "#poll-users-%s-%s"%(option, convId), "set", **args)


    @profile
    @dump_args
    def render_POST(self, request):
        d = None
        segmentCount = len(request.postpath)

        if segmentCount == 1 and request.postpath[0] == 'vote':
            d = self._vote(request)

        return self._epilogue(request, d)


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

        return self._epilogue(request, d)


class Poll(object):
    implements(IPlugin, IItemType)
    itemType = "poll"
    position = 5
    hasIndex = True
    indexFields = {'options':{'template':'poll_option_%s','type':'keyvals'}}
    monitoredFields = {'meta':['poll_options', 'comment']}

    def renderShareBlock(self, request, isAjax):
        t.renderScriptBlock(request, "poll.mako", "share_poll",
                            not isAjax, "#sharebar", "set", True,
                            attrs={"publisherName": "poll"},
                            handlers={"onload": "(function(obj){$$.publisher.load(obj);$('#share-poll-options').delegate('.input-wrap:last-child','focus',function(event){$(event.target.parentNode).clone().appendTo('#share-poll-options').find('input:text').blur();});})(this);"})


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("poll.mako", "poll_root", **args)
        else:
            return t.getBlock("poll.mako", "poll_root", args=[convId, isQuoted], **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def fetchData(self, args, convId=None, userId=None, columns=[]):
        convId = convId or args["convId"]
        myId = userId or args.get("myKey", None)

        conv = yield db.get_slice(convId, "items",
                                  ['options', 'counts'].extend(columns))
        conv = utils.supercolumnsToDict(conv, True)
        conv.update(args.get("items", {}).get(convId, {}))

        options = conv["options"] if conv.has_key("options") else None
        if not options:
            raise errors.InvalidRequest("The poll does not have any options")

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
    def create(self, request, myId, myOrgId, convId, richText=False):
        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                        constants.POST_PREVIEW_LENGTH,
                                        richText=richText)
        end = utils.getRequestArg(request, "end")
        start = utils.getRequestArg(request, "start")
        options = utils.getRequestArg(request, "options", multiValued=True)
        showResults = utils.getRequestArg(request, "show") or 'True'
        options = [option for option in options if option]

        if not comment:
            raise errors.MissingParams([_('Question')])
        if len(options) < 2 :
            raise errors.MissingParams([_('Add atleast two options to choose from')])

        item, attachments = yield utils.createNewItem(request, self.itemType, myId, myOrgId, richText=richText)

        meta = {"comment": comment, "showResults": showResults}
        if snippet:
            meta["snippet"] = snippet

        if start:
            meta["poll_start"] = start
        if end:
            meta["poll_end"] = end

        pollOptions = " ".join(options)
        meta["poll_options"] = pollOptions  # XXX: Required for keyword monitoring

        options = OrderedDict([('%02d'%(x), options[x]) for x in range(len(options))])
        item["options"] = options
        item["meta"].update(meta)

        defer.returnValue((item, attachments))


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
