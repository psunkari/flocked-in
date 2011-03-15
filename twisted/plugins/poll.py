import time
import uuid

from zope.interface     import implements
from twisted.plugin     import IPlugin
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, utils, base, errors
from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IAuthInfo
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

        conv = yield Db.get_slice(convId, "items", ["meta", 'options', 'counts'])
        if not len(conv):
            raise errors.InvalidRequest()
        conv = utils.supercolumnsToDict(conv, True)

        options = conv["options"] if conv.has_key("options") else None
        if not options:
            raise errors.InvalidRequest()

        toFetchUsers.add(conv["meta"]["owner"])

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


poll = Poll()
