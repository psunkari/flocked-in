import json
from twisted.internet   import defer

from social             import db, utils, base, tags, _, config, errors
from social             import template as t
from social.isocial     import IAuthInfo


class FeedbackResource(base.BaseResource):
    isLeaf = True
    _templates = ['item.mako']

    def renderFeedbackForm(self, request):
        """render feedback dialog."""
        t.renderScriptBlock(request, "item.mako", "feedbackDialog",
                            False, "#feedback-dlg", "set")
        return True

    @defer.inlineCallbacks
    def postFeedback(self, request):
        """creates a feedback item with feedback, feedback-{mood} tags.
        Push item to feeback, feedback-{mood} tag followers.
        Note: Item is owned by feedback-domain/synovel.com, not user sending
        the feedback. Only users of feedback-domain/synovel.com can access
        the item.
        """
        comment = utils.getRequestArg(request, 'comment')
        mood = utils.getRequestArg(request, 'mood')
        if not mood or not comment:
            raise errors.MissingParams([_("Feedback")])

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        tagName = 'feedback'
        moodTagName = 'feedback-' + mood

        feedbackDomain = config.get('Feedback', 'Domain') or 'synovel.com'
        cols = yield db.get_slice(feedbackDomain, 'domainOrgMap')
        if not cols:
            raise errors.ConfigurationError("feedbackDomain is invalid!")

        # Only one org exists per domain
        synovelOrgId = cols[0].column.name

        tagId, tag = yield tags.ensureTag(request, tagName, synovelOrgId)
        moodTagId, moodTag = yield tags.ensureTag(request, moodTagName,
                                                  synovelOrgId)

        # Anyone in synovel can receive feedback.
        acl = {'accept': {'orgs': [synovelOrgId]}}
        acl = json.dumps(acl)
        synovelOrg = base.Entity(synovelOrgId)
        yield synovelOrg.fetchData()
        # createNewItem expects an entity object with has org in basic info.
        # organizations wont have 'org' set.
        synovelOrg.basic['org'] = synovelOrgId

        item = yield utils.createNewItem(request, 'feedback', synovelOrg,
                                         acl, subType=mood)
        item['meta']['org'] = synovelOrgId
        item['meta']['userId'] = myId
        item['meta']['userOrgId'] = orgId
        item['meta']['comment'] = comment
        item['tags'] = {tagId: synovelOrgId, moodTagId: synovelOrgId}

        itemId = utils.getUniqueKey()

        tagItemCount = int(tag['itemsCount'])
        moodTagItemCount = int(moodTag['itemsCount'])
        if tagItemCount % 10 == 7:
            tagItemCount = yield db.get_count(tagId, "tagItems")
        if moodTagItemCount % 10 == 7:
            moodTagItemCount = yield db.get_count(moodTagId, "tagItems")

        tagItemCount += 1
        moodTagItemCount += 1

        # Finally save the feedback
        yield db.batch_insert(itemId, "items", item)
        yield db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])
        yield db.insert(moodTagId, "tagItems", itemId, item["meta"]["uuid"])
        yield db.insert(synovelOrgId, "orgTags", str(tagItemCount),
                        "itemsCount", tagId)
        yield db.insert(synovelOrgId, "orgTags", str(moodTagItemCount),
                        "itemsCount", moodTagId)

        cols = yield db.multiget_slice([tagId, moodTagId], "tagFollowers")
        followers = utils.multiColumnsToDict(cols)
        followers = set(followers[tagId].keys() + followers[moodTagId].keys())

        value = {"feed": {item['meta']['uuid']: itemId}}
        muts = dict([(x, value) for x in followers])
        if muts:
            yield db.batch_mutate(muts)

    def render_GET(self, request):
        d = self.renderFeedbackForm(request)
        return self._epilogue(request, d)

    def render_POST(self, request):
        d = self.postFeedback(request)
        return self._epilogue(request, d)
