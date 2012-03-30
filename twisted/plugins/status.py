from zope.interface     import implements
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import db, utils, errors, _, constants, validators
from social             import template as t
from social.isocial     import IItemType
from social.logging     import profile, dump_args


class ValidateStatus(validators.SocialSchema):
    comment = validators.TextWithSnippet(missingType='status')


class Status(object):
    implements(IPlugin, IItemType)
    itemType = "status"
    position = 1
    hasIndex = True
    monitoredFields = {'meta': ['comment']}
    displayNames = ('Status', 'Statuses')

    def renderShareBlock(self, request, isAjax):
        t.renderScriptBlock(request, "feed.mako", "share_status",
                            not isAjax, "#sharebar", "set", True,
                            attrs={"publisherName": "status"},
                            handlers={"onload": "(function(obj){$$.publisher.load(obj)})(this);"})

    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return t.getBlock("item.mako", "render_status", **args)
        else:
            return t.getBlock("item.mako", "render_status",
                              args=[convId, isQuoted], **args)

    def fetchData(self, args, convId=None):
        return defer.succeed(set())

    @profile
    @validators.Validate(ValidateStatus)
    @defer.inlineCallbacks
    @dump_args
    def create(self, request, me, convId, richText=False, data=None):
        comment, snippet = data['comment']

        item = yield utils.createNewItem(request, self.itemType,
                                         me, richText=richText)
        meta = {"comment": comment}
        if snippet:
            meta["snippet"] = snippet

        item["meta"].update(meta)
        defer.returnValue(item)

    @defer.inlineCallbacks
    def delete(self, myId, itemId, conv):
        yield db.get_slice(itemId, "entities")

    def getResource(self, isAjax):
        return None

status = Status()
