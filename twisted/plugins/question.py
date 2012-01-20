import time
import uuid

from zope.interface     import implements
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import db, base, utils, errors, _, constants
from social             import template as t
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.logging     import profile, dump_args, log


class Question(object):
    implements(IPlugin, IItemType)
    itemType = "question"
    position = 2
    hasIndex = True
    monitorFields = {'meta':['comment']}

    def renderShareBlock(self, request, isAjax):
        t.renderScriptBlock(request, "feed.mako", "share_question",
                            not isAjax, "#sharebar", "set", True,
                            attrs={"publisherName": "question"},
                            handlers={"onload": "(function(obj){$$.publisher.load(obj)})(this);"})


    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("item.mako", "render_status", **args)
        else:
            return t.getBlock("item.mako", "render_status", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request, myId, myOrgId, richText=False):
        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                        constants.POST_PREVIEW_LENGTH, richText=richText)

        if not comment:
            raise errors.MissingParams([_('Question')])

        item, attachments = yield utils.createNewItem(request, self.itemType,
                                                      myId, myOrgId,
                                                      richText=richText)
        meta = {"comment": comment}
        if snippet:
            meta['snippet'] = snippet

        item["meta"].update(meta)
        defer.returnValue((item, attachments))

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield db.get_slice(itemId, "entities")


    def getResource(self, isAjax):
        return None




question = Question()
