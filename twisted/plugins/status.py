import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, errors
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock


class Status(object):
    implements(IPlugin, IItemType)
    itemType = "status"
    position = 1
    hasIndex = True

    def shareBlockProvider(self):
        return ("feed.mako", "share_status")

    def rootHTML(self, convId, args):
        if "convId" in args:
            return getBlock("item.mako", "renderStatus", **args)
        else:
            return getBlock("item.mako", "renderStatus", args=[convId], **args)


    @defer.inlineCallbacks
    def fetchData(self, args, convId=None):
        convId = convId or args["convId"]
        toFetchEntities = set()

        conv = yield Db.get_slice(convId, "items", ['meta'])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.MissingParams()

        toFetchEntities.add(conv["meta"]["owner"])
        args.setdefault("items", {})[convId] = conv

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


    @defer.inlineCallbacks
    def create(self, request):
        target = utils.getRequestArg(request, "target")
        comment = utils.getRequestArg(request, "comment")

        if not comment:
            raise errors.MissingParams()

        convId = utils.getUniqueKey()
        item = utils.createNewItem(request, self.itemType)
        meta = {"comment": comment}
        if target:
            meta["target"] = target

        item["meta"].update(meta)

        yield Db.batch_insert(convId, "items", item)
        defer.returnValue((convId, item))


    def getResource(self, isAjax):
        return None


status = Status()
