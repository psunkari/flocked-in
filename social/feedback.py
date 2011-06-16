from twisted.internet   import defer
from twisted.python     import log
from twisted.web        import server

from social             import db, utils, base, tags, _, config
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo


class FeedbackResource(base.BaseResource):
    isLeaf=True

    @defer.inlineCallbacks
    def renderFeedbackForm(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        args["users"] = [myId]
        args["entities"] = {myId:args["me"]}
        args["title"] = _('Feedback')
        yield renderScriptBlock(request, "item.mako", "feedbackDialog", False,
                                "#feedback-dlg", "set", **args)


    @defer.inlineCallbacks
    def postFeedback(self, request):
        comment = utils.getRequestArg(request, 'comment')
        mood = utils.getRequestArg(request, 'mood')
        if not mood or not comment:
            raise errors.MissingParams()
        
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        tagName = 'feedback'
        moodTagName = 'feedback-'+mood

        feedbackDomain = config.get('Feedback', 'Domain') or 'synovel.com'
        cols = yield db.get_slice(feedbackDomain, 'domainOrgMap')
        if not cols:
            raise errors.InvalidRequest()

        # Only one org exists per domain
        synovelOrgId = cols[0].column.name

        tagId, tag = yield tags.ensureTag(request, tagName, synovelOrgId)
        moodTagId, moodTag = yield tags.ensureTag(request, moodTagName, synovelOrgId)

        # Anyone in synovel can receive feedback.
        acl = {'accept':{'orgs':[synovelOrgId]}}

        item = utils.createNewItem(request, itemType='feedback',
                                   ownerId=synovelOrgId, acl=acl,
                                   subType=mood,
                                   ownerOrgId=synovelOrgId)
        item['meta']['userId'] = myId
        item['meta']['userOrgId'] = args['orgKey']
        item['meta']['comment'] = comment
        item['tags'] = {tagId:synovelOrgId, moodTagId:synovelOrgId}

        itemId = utils.getUniqueKey()

        # XXX: Use cached values instead of calling get_count everytime
        tagItemCount = yield db.get_count(tagId, "tagItems")
        moodTagItemCount = yield db.get_count(moodTagId, "tagItems")

        tagItemCount += 1
        moodTagItemCount += 1

        # Finally save the feedback
        yield db.batch_insert(itemId, "items", item)
        yield db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])
        yield db.insert(moodTagId, "tagItems", itemId, item["meta"]["uuid"])
        yield db.insert(synovelOrgId, "orgTags", str(tagItemCount), "itemsCount", tagId)
        yield db.insert(synovelOrgId, "orgTags", str(moodTagItemCount), "itemsCount", moodTagId)


    def render_GET(self, request):
        d = self.renderFeedbackForm(request)
        return self._epilogue(request, d)


    def render_POST(self, request):
        d = self.postFeedback(request)
        return self._epilogue(request, d)

