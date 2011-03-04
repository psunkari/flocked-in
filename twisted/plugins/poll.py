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
from social             import feed
from social.template    import renderScriptBlock, render
from social.auth        import IAuthInfo
from social.isocial     import IItem
from social             import errors


class Poll(object):
    implements(IPlugin, IItem)
    itemType = "poll"


    @defer.inlineCallbacks
    def getRoot(self, convId, myKey):

        toFetchUsers = set()
        item = yield Db.get_slice(convId, "items", ["meta", 'options'])
        item = utils.supercolumnsToDict(item)
        toFetchUsers.add(item["meta"]["owner"])
        toFetchUsers.add(myKey)


        if not item:
            raise errors.InvalidRequest()

        options = item["options"] if item.has_key("options") else None
        if not options:
            raise errors.InvalidRequest()

        users = yield Db.multiget_slice(toFetchUsers, "users", ["basic"])
        users = utils.multiSuperColumnsToDict(users)

        myVote = yield Db.get_slice(myKey, "userVotes", [convId])
        myVote = myVote[0].column.value if myVote else ''
        startTime = item['meta'].get('start', None)
        endTime = item['meta'].get('end', None)
        showResults = item['meta'].get('showResults', 'True') == True
        if not showResults:
            # FIX: endTime is String. convert to time
            if not endTime or time.gmtime() > endTime:
                showResults = "True"

        items = {convId: item}
        myLikes = {convId:[]}
        responses = {convId: []}
        defer.returnValue({"items": items,
                           "myVote": myVote,
                           "responses": responses,
                           "users": users,
                           "myLikes": myLikes,
                           "showResults": showResults})


    @defer.inlineCallbacks
    def renderRoot(self, request, convId, args):

        script = args['script']
        landing = not args['ajax']
        toFeed = args['toFeed'] if args.has_key('toFeed') else False

        if script:
            if not toFeed:
                yield renderScriptBlock(request, "item.mako", "poll_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)
            else:
                # del args["convId"] is a workaround. getrid of it.
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
        question = utils.getRequestArg(request, "q")
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