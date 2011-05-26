from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import Db, utils, base, tags
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo


class FeedbackResource(base.BaseResource):
    isLeaf=True

    @defer.inlineCallbacks
    def renderFeedbackForm(self, request):

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        args["users"] = [myId]
        args["entities"] = {myId:args["me"]}
        args['title'] = 'feedback'
        yield renderScriptBlock(request, "item.mako", "feedbackDialog", False,
                                "#feedback-dlg", "set", **args)

    @defer.inlineCallbacks
    def postFeedback(self, request):

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        comment = utils.getRequestArg(request, 'comment')
        category = utils.getRequestArg(request, 'category')
        tagName = 'Users FeedBack'

        if not comment:
            request.redirect('/feed')
            defer.returnValue(None)

        cols = yield Db.get_slice('ashok@synovel.com', 'userAuth')
        if not cols:
            cols = yield Db.get_slice('ashok@example.com', 'userAuth')
        cols = utils.columnsToDict(cols)
        synovelOrgId = cols['org']
        itemOwner = cols['user']
        tagId, tag = yield tags.ensureTag(request, tagName, synovelOrgId)

        acl = {'accept':{'orgs':[synovelOrgId]}}

        meta = utils.createNewItem(request, itemType = 'status',
                                   ownerId = itemOwner, acl = acl,
                                   subType = 'feedback',
                                   ownerOrgId= synovelOrgId)
        meta['meta']['userId'] = myId
        meta['meta']['comment'] = comment
        meta['tags'] = {tagId: itemOwner}
        if category:
            meta['meta']['category'] = category

        itemId = utils.getUniqueKey()
        tagItemCount = yield Db.get_count(tagId, "tagItems")
        tagItemCount += 1

        yield Db.batch_insert(itemId, "items", meta)
        yield Db.insert(tagId, "tagItems", itemId, meta["meta"]["uuid"])
        yield Db.insert(synovelOrgId, "orgTags", str(tagItemCount), "itemsCount", tagId)


    def render_GET(self, request):
        d = self.renderFeedbackForm(request)
        return self._epilogue(request, d)


    def render_POST(self, request):
        d = self.postFeedback(request)
        return self._epilogue(request, d)


