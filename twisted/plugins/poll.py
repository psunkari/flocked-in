import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, utils, base, errors
from social.template    import renderScriptBlock, render, getBlock
from social.auth        import IAuthInfo
from social.isocial     import IItemType


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
    def fetchData(self, args, convId=None):
        toFetchUsers = set()
        toFetchGroups = set()
        convId = convId or args["convId"]
        myKey = args["myKey"]

        conv = yield Db.get_slice(convId, "items", ["meta", 'options'])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.InvalidRequest()

        options = conv["options"] if conv.has_key("options") else None
        if not options:
            raise errors.InvalidRequest()

        toFetchUsers.add(conv["meta"]["owner"])

        myVote = yield Db.get_slice(myKey, "userVotes", [convId])
        myVote = myVote[0].column.value if myVote else ''

        startTime = conv['meta'].get('start', None)
        endTime = conv['meta'].get('end', None)
        showResults = conv['meta'].get('showResults', 'True') == True

        if not showResults:
            # FIX: endTime is String. convert to time
            if not endTime or time.gmtime() > endTime:
                showResults = "True"

        args.setdefault("items", {})[convId] = conv
        args.setdefault("myVote", {})[convId] = myVote
        args.setdefault("showResults", {})[convId] = showResults

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
        myKey = request.getSession(IAuthInfo).username

        acl = utils.getRequestArg(request, 'acl') or 'public'
        end = utils.getRequestArg(request, "end")
        start = utils.getRequestArg(request, "start")
        options = request.args.get("options", [])
        question = utils.getRequestArg(request, "question")
        showResults = utils.getRequestArg(request, "show") or 'True'

        if not (question and options):
            raise errors.InvalidRequest()

        convId = utils.getUniqueKey()
        itemType = self.itemType
        timeuuid = uuid.uuid1().bytes

        meta = {}
        meta["acl"] = acl
        meta["type"] = itemType
        meta["uuid"] = timeuuid
        meta["owner"] = myKey
        meta["question"] = question
        meta["timestamp"] = "%s" % int(time.time())
        meta["showResults"] = showResults
        if start:
            # FIX: convert to gmt time
            meta["start"] = start
        if end:
            # FIX: convert to gmt time
            meta["end"] = end

        followers = {}
        followers[myKey] = ''

        options = dict([(option, '0') for option in options])

        yield Db.batch_insert(convId, "items", {'meta':meta,
                                                'options':options,
                                                'followers':followers})

        defer.returnValue([convId, timeuuid, acl])


    @defer.inlineCallbacks
    def post(self, request):
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


poll = Poll()
