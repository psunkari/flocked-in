
import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IItemType
from social             import Db, base, utils, errors
from social.logging     import profile, dump_args

class Links(object):
    implements(IPlugin, IItemType)
    itemType = "link"
    position = 3
    hasIndex = True
    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        templateFile = "feed.mako"
        renderDef = "share_link"

        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "link"},
                                handlers={"onload": "(function(obj){$$.publisher.load(obj)})(this);"})
    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("item.mako", "render_status", **args)
        else:
            return getBlock("item.mako", "render_status", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
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

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield Db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None
links = Links()
