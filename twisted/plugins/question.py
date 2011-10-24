import time
import uuid

from zope.interface     import implements
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import db, base, utils, errors, _, constants
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import profile, dump_args, log


class Question(object):
    implements(IPlugin, IItemType)
    itemType = "question"
    position = 2
    hasIndex = True
    indexFields = [('meta', 'comment'), ('meta', 'parent')]

    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        templateFile = "feed.mako"
        renderDef = "share_question"

        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "question"},
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
        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                        constants.POST_PREVIEW_LENGTH)
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        if not comment:
            raise errors.MissingParams([_('Question')])

        convId = utils.getUniqueKey()
        item, attachments = yield utils.createNewItem(request, self.itemType)
        meta = {"comment": comment}
        if snippet:
            meta['snippet'] = snippet

        item["meta"].update(meta)
        yield db.batch_insert(convId, "items", item)

        for attachmentId in attachments:
            timeuuid, fid, name, size, ftype  = attachments[attachmentId]
            val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
            yield db.insert(convId, "item_files", val, timeuuid, attachmentId)

        from social import fts
        fts.solr.updateIndex(convId, item, myOrgId, attachments)
        defer.returnValue((convId, item))

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None




question = Question()
