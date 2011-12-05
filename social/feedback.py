from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, tags, _, config, errors, feed
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.logging     import log


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
            raise errors.MissingParams([_("Feedback")])

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        tagName = 'feedback'
        moodTagName = 'feedback-'+mood

        feedbackDomain = config.get('Feedback', 'Domain') or 'synovel.com'
        cols = yield db.get_slice(feedbackDomain, 'domainOrgMap')
        if not cols:
            raise errors.ConfigurationError("feedbackDomain is invalid!")

        # Only one org exists per domain
        synovelOrgId = cols[0].column.name

        tagId, tag = yield tags.ensureTag(request, tagName, synovelOrgId)
        moodTagId, moodTag = yield tags.ensureTag(request, moodTagName, synovelOrgId)

        # Anyone in synovel can receive feedback.
        acl = {'accept':{'orgs':[synovelOrgId]}}

        item, attachments = yield utils.createNewItem(request, 'feedback',
                                                      synovelOrgId, synovelOrgId,
                                                      subType=mood)
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

        cols = yield db.multiget_slice([tagId, moodTagId], "tagFollowers")
        followers = utils.multiColumnsToDict(cols)
        followers = set(followers[tagId].keys() + followers[moodTagId].keys())

        value = {"feed":{item['meta']['uuid']: itemId}}
        muts = dict([(x, value) for x in followers])
        if muts:
            yield db.batch_mutate(muts)


    def render_GET(self, request):
        d = self.renderFeedbackForm(request)
        return self._epilogue(request, d)


    def render_POST(self, request):
        d = self.postFeedback(request)
        return self._epilogue(request, d)
