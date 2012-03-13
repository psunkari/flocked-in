import uuid
import time
import json
import cPickle as pickle

from twisted.internet   import defer

from social             import base, db, utils, plugins, constants, _, errors
from social             import template as t
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args
from social.validators  import ValidateComment, Validate, ValidateItem
from social             import validators
from social.core        import item as Item


class RemoveItem(validators.SocialSchema):
    id = validators.Item(arg='id', columns=['tags'])



class ItemResource(base.BaseResource):
    isLeaf = True
    _templates = ['item.mako', 'item-report.mako']

    """
    def paths(self):
        return  [('GET',    '/(?P<itemId>)/',               self._get),
                 ('GET',    '/(?P<itemId>)/comments/',      self._getComments),
                 ('GET',    '/(?P<itemId>)/likes/',         self._getLikes),
                 ('GET',    '/(?P<itemId>)/tags/',          self._getTags),
                 ('GET',    '/(?P<itemId>)/files/',         self._getFiles),

                 ('POST',   '/',                            self._new),
                 ('POST',   '/(?P<itemId>)/comments/',      self._comment),
                 ('POST',   '/(?P<itemId>)/likes/',         self._like),
                 ('POST',   '/(?P<itemId>)/tags/',          self._tag),

                 ('DELETE', '/(?P<itemId>)/',               self._delete),
                 ('DELETE', '/(?P<itemId>)/likes/',         self._unlike),
                 ('DELETE', '/(?P<itemId>)/tags/(?<tag>)',  self._untag)]
    """

    def _cleanupMissingComments(self, convId, missingIds, itemResponses):
        missingKeys = []
        for response in itemResponses:
            userKey, responseKey = response.column.value.split(':')
            if responseKey in missingIds:
                missingKeys.append(response.column.name)

        d1 = db.batch_remove({'itemResponses': [convId]}, names=missingKeys)
        d1.addCallback(lambda x: db.get_count(convId, "itemResponses"))
        d1.addCallback(lambda x: db.insert(convId, 'items', \
                                 str(x), 'responseCount', 'meta'))
        return d1

    @profile
    @defer.inlineCallbacks
    @dump_args
    def renderItem(self, request, toFeed=False):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgId"]

        convId, conv = yield utils.getValidItemId(request, "id", columns=['tags'])
        itemType = conv["meta"].get("type", None)

        if 'parent' in conv['meta']:
            raise errors.InvalidItem('conversation', convId)

        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        args['convId'] = convId
        args['isItemView'] = True
        args['items'] = {convId: conv}
        meta = conv["meta"]
        owner = meta["owner"]

        relation = Relation(myId, [])
        yield defer.DeferredList([relation.initGroupsList(),
                                  relation.initSubscriptionsList()])
        args["relations"] = relation

        if script and landing:
            t.render(request, "item.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "item.mako", "layout",
                                landing, "#mainbar", "set", **args)

        args["entities"] = {}
        toFetchEntities = set()
        toFetchTags = set(conv.get("tags", {}).keys())

        plugin = plugins[itemType] if itemType in plugins else None
        if plugin:
            entityIds = yield plugin.fetchData(args)
            toFetchEntities.update(entityIds)

        toFetchEntities.add(conv['meta']['owner'])
        if "target" in conv["meta"]:
            toFetchEntities.update(conv['meta']['target'].split(','))

        if conv['meta']['owner'] not in toFetchEntities:
            toFetchEntities.add(conv['meta']['owner'])
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        args["entities"] = entities

        renderers = []

        if script:
            t.renderScriptBlock(request, "item.mako", "conv_root",
                                landing, "#conv-root-%s > .conv-summary" % (convId),
                                "set", **args)

        convOwner = args["items"][convId]["meta"]["owner"]
        args["ownerId"] = convOwner
        if script:
            if itemType != "feedback":
                t.renderScriptBlock(request, "item.mako", "conv_owner",
                                    landing, "#conv-avatar-%s" % convId,
                                    "set", **args)
            else:
                feedbackType = conv['meta']['subType']
                t.renderScriptBlock(request, "item.mako", "feedback_icon",
                                    landing, "#conv-avatar-%s" % convId,
                                    "set", args=[feedbackType])

        # A copy of this code for fetching comments is present in _responses
        # Most changes here may need to be done there too.
        itemResponses = yield db.get_slice(convId, "itemResponses",
                                           start=start, reverse=True,
                                           count=constants.COMMENTS_PER_PAGE + 1)
        nextPageStart = itemResponses[-1].column.name\
                        if len(itemResponses) > constants.COMMENTS_PER_PAGE\
                        else None
        itemResponses = itemResponses[:-1] \
                        if len(itemResponses) > constants.COMMENTS_PER_PAGE\
                        else itemResponses
        responseKeys = []
        for response in itemResponses:
            userKey, responseKey = response.column.value.split(":")
            responseKeys.append(responseKey)
            toFetchEntities.add(userKey)
        responseKeys.reverse()

        subscriptions = list(relation.subscriptions)
        likes = yield db.get_slice(convId, "itemLikes", subscriptions) \
                            if subscriptions else defer.succeed([])
        toFetchEntities.update([x.column.name for x in likes])
        entities = base.EntitySet(toFetchEntities)
        d1 = entities.fetchData()
        d2 = db.multiget_slice(responseKeys, "items", ["meta"])
        d3 = db.multiget_slice(responseKeys + [convId], "itemLikes", [myId])
        d4 = db.get_slice(myOrgId, "orgTags", toFetchTags)\
                                    if toFetchTags else defer.succeed([])

        yield d1
        fetchedItems = yield d2
        myLikes = yield d3
        fetchedTags = yield d4

        fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
        myLikes = utils.multiColumnsToDict(myLikes)
        fetchedTags = utils.supercolumnsToDict(fetchedTags)

        # Do some error correction/consistency checking to ensure that the
        # response items actually exist. I don't know of any reason why these
        # items may not exist.
        missingIds = [x for x, y in fetchedItems.items() if not y]
        if missingIds:
            yield self._cleanupMissingComments(convId, missingIds, itemResponses)

        args["items"].update(fetchedItems)
        args["entities"].update(entities)
        args["myLikes"] = myLikes
        args["tags"] = fetchedTags
        args["responses"] = {convId: responseKeys}
        if nextPageStart:
            args["oldest"] = utils.encodeKey(nextPageStart)

        if script:
            t.renderScriptBlock(request, "item.mako", 'conv_footer',
                                landing, '#item-footer-%s' % convId,
                                'set', **args)
            t.renderScriptBlock(request, "item.mako", 'conv_tags',
                                landing, '#conv-tags-wrapper-%s' % convId, 'set',
                                handlers={"onload": "$('#conv-meta-wrapper-%s').removeClass('no-tags')" % convId} if toFetchTags else None, **args)
            t.renderScriptBlock(request, "item.mako", 'conv_comments',
                                landing, '#conv-comments-wrapper-%s' % convId, 'set', **args)
            t.renderScriptBlock(request, "item.mako", 'conv_comment_form',
                                landing, '#comment-form-wrapper-%s' % convId, 'set',
                                True, handlers={"onload": "(function(obj){$$.convs.load(obj);})(this);"}, **args)

            numLikes = int(conv["meta"].get("likesCount", "0"))
            if numLikes:
                numLikes = int(conv["meta"].get("likesCount", "0"))
                iLike = myId in args["myLikes"].get(convId, [])
                t.renderScriptBlock(request, "item.mako", 'conv_likes',
                                    landing, '#conv-likes-wrapper-%s' % convId, 'set',
                                    args=[convId, numLikes, iLike, [x.column.name for x in likes]],
                                    entities=args['entities'])

        if plugin and hasattr(plugin, 'renderItemSideBlock'):
            plugin.renderItemSideBlock(request, landing, args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            t.render(request, "item.mako", **args)

    @profile
    @Validate(validators.NewItem)
    @defer.inlineCallbacks
    @dump_args
    def _new(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        me = args['me']
        landing = not self._ajax
        authInfo = request.getSession(IAuthInfo)
        convType = data['type']
        convId, conv, keywords = yield Item.new(request, authInfo, convType)
        if keywords:
            block = t.getBlock('item.mako', 'requireReviewDlg', keywords=keywords)
            request.write('$$.convs.reviewRequired(%s);' % json.dumps(block))
            return

        target = conv['meta'].get('target', None)
        toFetchEntities = set()
        if target:
            toFetchEntities.update(target.split(','))

        convType = utils.getRequestArg(request, "type")
        plugin = plugins[convType]
        entityIds = yield plugin.fetchData(args, convId)
        toFetchEntities.update(entityIds)
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        entities.update(args['me'])

        relation = Relation(myId, [])
        yield relation.initGroupsList()

        data = {"items": {convId: conv}, "relations": relation,
                "entities": entities, "script": True}
        args.update(data)
        onload = "(function(obj){$$.convs.load(obj);$('#sharebar-attach-uploaded').empty();})(this);"
        t.renderScriptBlock(request, "item.mako", "item_layout",
                            False, "#user-feed", "prepend", args=[convId, 'conv-item-created'],
                            handlers={"onload": onload}, **args)

        defaultType = plugins.keys()[0]
        plugins[defaultType].renderShareBlock(request, True)
        if plugin and hasattr(plugin, 'renderFeedSideBlock'):
            #TODO: Determine the blockType
            if target:
                entityId = target.split(',')[0]
                args["groupId"] = target.split(',')[0]
            else:
                #No better way to find out if this item was created from the
                # user's feed page or from the company feed page
                referer = request.getHeader('referer')
                entityId = myId

            request.write("$('#feed-side-block-container').empty();")
            yield plugins["event"].renderFeedSideBlock(request, landing,
                                                         entityId, args)

    @profile
    @Validate(ValidateItem)
    @defer.inlineCallbacks
    @dump_args
    def _like(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args['orgId']

        itemId, item = data['id']
        item = yield Item.like(itemId, item, myId, orgId, args['me'])
        if not item:
            return

        args["items"] = {itemId: item}
        args["myLikes"] = {itemId: [myId]}
        convId = item['meta'].get('parent', itemId)

        if itemId != convId:
            t.renderScriptBlock(request, "item.mako", "item_footer", False,
                                "#item-footer-%s" % (itemId), "set",
                                args=[itemId], **args)
        else:
            relation = Relation(myId, [])
            yield relation.initSubscriptionsList()
            subscriptions = list(relation.subscriptions)
            if subscriptions:
                likes = yield db.get_slice(convId, "itemLikes", subscriptions)
                likes = [x.column.name for x in likes]
            else:
                likes = []

            isFeed = (data['_pg'] != "/item")
            hasComments = False
            hasLikes = True if likes else False
            toFetchEntities = set(likes)
            if not isFeed:
                hasComments = True
            else:
                feedItems = yield db.get_slice(myId, "feedItems", [convId])
                feedItems = utils.supercolumnsToDict(feedItems)
                for tuuid in feedItems.get(convId, {}):
                    val = feedItems[convId][tuuid]
                    rtype = val.split(":")[0]
                    if rtype == "C":
                        hasComments = True

            entities = {}
            entities = base.EntitySet(toFetchEntities)
            if toFetchEntities:
                yield entities.fetchData()
            args["entities"] = entities
            likesCount = int(item['meta']["likesCount"])

            handler = {"onload": "(function(){$$.convs.showHideComponent('%s', 'likes', true)})();" % (convId)}
            t.renderScriptBlock(request, "item.mako", "conv_footer", False,
                                "#item-footer-%s" % (itemId), "set",
                                args=[itemId, hasComments, hasLikes], **args)

            t.renderScriptBlock(request, "item.mako", 'conv_likes', False,
                                '#conv-likes-wrapper-%s' % convId, 'set', True,
                                args=[itemId, likesCount, True, likes], handlers=handler, **args)

    @profile
    @Validate(ValidateItem)
    @defer.inlineCallbacks
    @dump_args
    def _unlike(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args['orgId']

        itemId, item = data['id']
        item = yield Item.unlike(itemId, item, myId, orgId)
        if not item:
            return

        args["items"] = {itemId: item}
        args["myLikes"] = {itemId: []}
        likesCount = int(item["meta"]["likesCount"])
        convId = item["meta"].get('parent', itemId)

        if itemId != convId:
            t.renderScriptBlock(request, "item.mako", "item_footer", False,
                                 "#item-footer-%s" % (itemId), "set",
                                 args=[itemId], **args)
        else:
            relation = Relation(myId, [])
            yield relation.initSubscriptionsList()

            toFetchEntities = set()
            likes = []
            subscriptions = list(relation.subscriptions)
            if subscriptions:
                likes = yield db.get_slice(convId, "itemLikes", subscriptions)
                likes = [x.column.name for x in likes]
                toFetchEntities = set(likes)

            feedItems = yield db.get_slice(myId, "feedItems", [convId])
            feedItems = utils.supercolumnsToDict(feedItems)
            isFeed = (utils.getRequestArg(request, "_pg") != "/item")
            hasComments = False
            if not isFeed:
                hasComments = True
            else:
                feedItems = yield db.get_slice(myId, "feedItems", [convId])
                feedItems = utils.supercolumnsToDict(feedItems)
                for tuuid in feedItems.get(convId, {}):
                    val = feedItems[convId][tuuid]
                    rtype = val.split(":")[0]
                    if rtype == "C":
                        hasComments = True

            entities = base.EntitySet(toFetchEntities)
            if toFetchEntities:
                yield entities.fetchData()

            args["entities"] = entities

            handler = {"onload": "(function(){$$.convs.showHideComponent('%s', 'likes', false)})();" % (convId)} if not likes else None
            t.renderScriptBlock(request, "item.mako", "conv_footer", False,
                                "#item-footer-%s" % (itemId), "set",
                                args=[itemId, hasComments, likes], **args)
            t.renderScriptBlock(request, "item.mako", 'conv_likes', False,
                                '#conv-likes-wrapper-%s' % convId, 'set', True,
                                args=[itemId, likesCount, False, likes], handlers=handler, **args)

    @Validate(ValidateComment)
    @defer.inlineCallbacks
    def _comment(self, request, data=None):

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        convId, conv = data['parent']
        comment, snippet = data['comment']
        review = data['_review']

        itemId, convId, items, keywords = yield Item._comment(convId, conv, comment, snippet, myId, orgId, False, review)

        if keywords:
            block = t.getBlock('item.mako', 'requireReviewDlg', keywords=keywords, convId=convId)
            request.write('$$.convs.reviewRequired(%s, "%s");' % (json.dumps(block), convId))
            return

        # Finally, update the UI
        entities = base.EntitySet([myId])
        yield entities.fetchData()
        args = {"entities": entities, "items": items, "me": entities[myId]}

        numShowing = utils.getRequestArg(request, "nc") or "0"
        numShowing = int(numShowing) + 1
        responseCount = items[convId]['meta']['responseCount']
        isItemView = (utils.getRequestArg(request, "_pg") == "/item")
        t.renderScriptBlock(request, 'item.mako', 'conv_comments_head',
                            False, '#comments-header-%s' % (convId), 'set',
                            args=[convId, responseCount, numShowing, isItemView], **args)

        t.renderScriptBlock(request, 'item.mako', 'conv_comment', False,
                            '#comments-%s' % convId, 'append', True,
                            handlers={"onload": "(function(){$('.comment-input', '#comment-form-%s').val(''); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, convId, numShowing)},
                            args=[convId, itemId], **args)

    @profile
    @Validate(ValidateItem)
    @defer.inlineCallbacks
    @dump_args
    def _likes(self, request, data=None):
        itemId, item = data['id']
        entities, users = yield Item.likes(itemId, item)
        args = {"users": users, "entities": entities}
        itemType = item['meta'].get('type', 'comment')
        ownerId = item["meta"]["owner"]
        args['title'] = _("People who like %s's %s") %\
                          (utils.userName(ownerId, entities[ownerId]), _(itemType))

        t.renderScriptBlock(request, "item.mako", "userListDialog", False,
                            "#likes-dlg-%s" % (itemId), "set", **args)

    @profile
    @Validate(validators.ItemResponses)
    @defer.inlineCallbacks
    @dump_args
    def _responses(self, request, data=None):
        convId, conv = data['id']
        start = data['start']
        isFeed = data['_pg'] != '/item'
        showing = data["nc"]
        start = utils.decodeKey(start)
        myId = request.getSession(IAuthInfo).username
        landing = not self._ajax
        me = base.Entity(myId)

        responseCount = int(conv["meta"].get("responseCount", "0"))

        if isFeed and responseCount > constants.MAX_COMMENTS_IN_FEED:
            request.write("$$.fetchUri('/item?id=%s');" % convId)
            return
        ret = yield Item.responses(myId, convId, conv, start)

        yield me.fetchData()
        args = ret
        args.update({"convId": convId, "isFeed": isFeed, "me": me})

        if isFeed:
            args["isItemView"] = False
            showing = len(args['responses'][convId])
            handler = {"onload": "(function(){$$.convs.showHideComponent('%s', 'comments', true); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, convId, showing)}
            t.renderScriptBlock(request, "item.mako", 'conv_comments',
                                landing, '#conv-comments-wrapper-%s' % convId,
                                'set', True, handlers=handler, **args)
        else:
            showing = int(showing) + len(args['responses'][convId])
            args["showing"] = showing
            args["total"] = int(args["items"][convId]["meta"].get("responseCount", "0"))
            args["isItemView"] = True

            t.renderScriptBlock(request, "item.mako", 'conv_comments_head',
                                landing, '#comments-header-%s' % convId,
                                'set', **args)
            t.renderScriptBlock(request, "item.mako", 'conv_comments_only',
                                landing, '#comments-%s' % convId, 'prepend', True,
                                handlers={"onload": "(function(){$('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, showing)},
                                **args)

    @profile
    @Validate(validators.ValidateTag)
    @defer.inlineCallbacks
    @dump_args
    def _tag(self, request, data):
        tagName = data['tag']
        (itemId, item) = data['id']

        if not tagName:
            return

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        tagId, tag = yield Item.tag(itemId, item, tagName, myId, orgId)

        t.renderScriptBlock(request, "item.mako", 'conv_tag', False,
                            '#conv-tags-%s' % itemId, "append", True,
                            handlers={"onload": "(function(){$('input:text', '#addtag-form-%s').val('');})();" % itemId},
                            args=[itemId, tagId, tag["title"]])

    @profile
    @Validate(validators.ValidateTagId)
    @defer.inlineCallbacks
    @dump_args
    def _untag(self, request, data):
        itemId, item = data['id']
        tagId, tag = data['tag']

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        yield Item.untag(itemId, item, tagId, tag, myId, orgId)
        request.write("$('#conv-tags-%s').children('[tag-id=\"%s\"]').remove();" % (itemId, tagId))

    @Validate(RemoveItem)
    @defer.inlineCallbacks
    def _remove(self, request, data=None):
        itemId, item = data['id']

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        convId = item['meta']['parent'] if 'parent' in item['meta'] else itemId
        yield Item.removeFromFeed(itemId, item, myId, orgId)
        request.write("$$.convs.remove('%s', '%s');" % (convId, itemId))

    @Validate(RemoveItem)
    @defer.inlineCallbacks
    def _delete(self, request, data=None):
        itemId, item = data['id']

        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        convId = item['meta']['parent'] if 'parent' in item['meta'] else itemId
        yield Item.delete(itemId, item, myId, orgId)
        request.write("$$.convs.remove('%s', '%s');" % (convId, itemId))

        #target = conv['meta'].get('target', None)

        #if plugin and hasattr(plugin, 'renderFeedSideBlock') and not comment:
        #    #TODO: Determine the blockType
        #    if target:
        #        entityId = target.split(',')[0]
        #        args["groupId"] = target.split(',')[0]
        #    else:
        #        #No better way to find out if this item was created from the
        #        # user's feed page or from the company feed page
        #        referer = request.getHeader('referer')
        #        entityId = myId

        #   request.write("$('#feed-side-block-container').empty();")
        #    yield plugins["event"].renderFeedSideBlock(request, landing,
        #                                                entityId, args)

    @defer.inlineCallbacks
    def _renderReportDialog(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        itemId, item = yield utils.getValidItemId(request, "id")
        args = {}

        itemType = item["meta"].get("type")

        args['title'] = _("Report this %s") % itemType
        args['convId'] = itemId

        t.renderScriptBlock(request, "item-report.mako", "report_dialog", False,
                            "#report-dlg-%s" % (itemId), "set", **args)

    @defer.inlineCallbacks
    def _renderReport(self, request, partial=False):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        convId, conv = yield utils.getValidItemId(request, "id", columns=["reports"])
        if 'parent' in conv['meta']:
            raise errors.InvalidItem('conversation', convId)

        args["entities"] = {}
        toFetchEntities = set()

        args['convId'] = convId
        args['items'] = {convId: conv}
        convMeta = conv["meta"]
        convType = convMeta.get("type", None)

        relation = Relation(myId, [])
        yield relation.initGroupsList()
        args["relations"] = relation

        if script and landing:
            t.render(request, "item-report.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "item-report.mako", "layout",
                                landing, "#mainbar", "set", **args)

        plugin = plugins[convType] if convType in plugins else None
        if plugin:
            entityIds = yield plugin.fetchData(args)
            toFetchEntities.update(entityIds)

        convOwner = convMeta['owner']
        toFetchEntities.add(convOwner)
        if "target" in convMeta:
            toFetchEntities.update(convMeta['target'].split(','))
        if "reportId" in convMeta:
            toFetchEntities.add(convMeta['reportedBy'])

        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        args["entities"] = entities
        args["ownerId"] = convOwner

        if script:
            t.renderScriptBlock(request, "item.mako", "conv_root",
                                landing, "#conv-root-%s > .conv-summary" % (convId),
                                "set", **args)

            t.renderScriptBlock(request, "item-report.mako", 'conv_footer',
                                landing, '#item-footer-%s' % convId,
                                'set', **args)

            if convType != "feedback":
                t.renderScriptBlock(request, "item.mako", "conv_owner",
                                    landing, "#conv-avatar-%s" % convId,
                                    "set", **args)
            else:
                feedbackType = conv['meta']['subType']
                t.renderScriptBlock(request, "item.mako", "feedback_icon",
                                    landing, "#conv-avatar-%s" % convId,
                                    "set", args=[feedbackType])

        yield self._renderReportResponses(request, convId, convMeta, args)

        if not script:
            t.render(request, "item-report.mako", **args)

    @defer.inlineCallbacks
    def _renderReportResponses(self, request, convId, convMeta, args):
        reportId = convMeta.get('reportId', None)
        args['convMeta'] = convMeta
        script = args["script"]
        myId = args["myId"]
        landing = not self._ajax

        if script:
            t.renderScriptBlock(request, "item-report.mako", "item_report",
                                landing, "#report-contents", "set", **args)

        if reportId:
            reportResponses = yield db.get_slice(reportId, "itemResponses")
            reportResponseKeys, toFetchEntities = [], []
            reportResponseActions = {}

            for response in reportResponses:
                userKey, responseKey, action = response.column.value.split(":")
                reportResponseKeys.append(responseKey)
                reportResponseActions[responseKey] = action

            fetchedResponses = yield db.multiget_slice(reportResponseKeys, "items", ["meta"])
            fetchedResponses = utils.multiSuperColumnsToDict(fetchedResponses)

            args["reportId"] = reportId
            args["reportItems"] = fetchedResponses
            args["responseKeys"] = reportResponseKeys
            args["reportResponseActions"] = reportResponseActions

            #Show comments from report only if I am the owner or the reporter
            if script and myId in [convMeta["owner"], convMeta["reportedBy"]]:
                t.renderScriptBlock(request, "item-report.mako", 'report_comments',
                                    landing, '#report-comments', 'set', **args)

    @defer.inlineCallbacks
    def _submitReport(self, request, action):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                            constants.COMMENT_PREVIEW_LENGTH)
        orgId = args['orgId']
        isNewReport = False
        timeUUID = uuid.uuid1().bytes

        convId, conv = yield utils.getValidItemId(request, "id")
        convMeta = conv["meta"]
        convOwnerId = convMeta["owner"]
        convType = convMeta["type"]
        convACL = convMeta["acl"]
        toFetchEntities = set([myId, convOwnerId])

        if "reportId" in convMeta:
            reportId = convMeta["reportId"]
            isNewReport = False
            toFetchEntities.add(convMeta['reportedBy'])
        else:
            isNewReport = True
            reportId = utils.getUniqueKey()

        if isNewReport and convOwnerId == myId:
            raise errors.InvalidRequest(_("You cannot report your own Item. \
                                                Delete the item instead"))

        toFetchEntities.remove(myId)
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        entities.update({myId: args["me"]})

        if myId == convOwnerId:
            if action not in ["accept", "repost"]:
                raise errors.InvalidRequest(_('Invalid action was performed on the report'))

            convReport = {"reportStatus": action}
            yield db.batch_insert(convId, "items", {"meta": convReport})

            if action == "accept":
                # Owner removed the comment. Delete the item from his feed
                yield Item.deleteItem(convId, myId, orgId)
                request.write("$$.fetchUri('/feed/');")
                request.write("$$.alerts.info('%s')" % _("Your item has been deleted"))
                request.finish()
            else:
                # Owner posted a reply, so notify reporter of the same
                yield Item._notify("RFC", convId, timeUUID, convType=convType,
                               convOwnerId=convOwnerId, myId=myId, entities=entities,
                               me=args["me"], reportedBy=convMeta["reportedBy"])
        else:
            if action not in ["report", "repost", "reject"]:
                raise errors.InvalidRequest(_('Invalid action was performed on the report'))

            if isNewReport:
                # Update Existing Item Information with Report Meta
                newACL = pickle.dumps({"accept": {"users": [convOwnerId, myId]}})
                convReport = {"reportedBy": myId, "reportId": reportId,
                              "reportStatus": "pending", "state": "flagged"}
                convMeta.update(convReport)
                yield db.batch_insert(convId, "items", {"meta": convReport})

                reportLink = """&#183;<a class="button-link" title="View Report" href="/item/report?id=%s"> View Report</a>""" % convId
                request.write("""$("#item-footer-%s").append('%s');""" % (convId, reportLink))
                yield Item._notify("FC", convId, timeUUID, convType=convType, entities=entities,
                              convOwnerId=convOwnerId, myId=myId, me=args["me"])
            else:
                if action == "repost":
                    # Remove the reportId key, so owner cannot post any comment
                    yield db.batch_remove({'items': [convId]},
                                            names=["reportId", "reportStatus",
                                                   "reportedBy", "state"],
                                            supercolumn='meta')

                    oldReportMeta = {"reportedBy": convMeta["reportedBy"],
                                     "reportId": reportId}

                    # Save the now resolved report in items and remove its
                    #  reference in the item meta so new reporters wont't see
                    #  old reports
                    timestamp = str(int(time.time()))
                    yield db.insert(convId, "items", reportId, timestamp, "reports")
                    yield db.batch_insert(reportId, "items", {"meta": oldReportMeta})

                    # Notify the owner that the report has been withdrawn
                    yield Item._notify("UFC", convId, timeUUID, convType=convType,
                                  convOwnerId=convOwnerId, myId=myId,
                                  entities=entities, me=args["me"])

                elif action  in ["reject", "report"]:
                    # Reporter rejects the comment by the owner or reports the
                    #  same item again.
                    convReport = {"reportStatus": "pending"}
                    yield Item._notify("RFC", convId, timeUUID, convType=convType,
                                  convOwnerId=convOwnerId, myId=myId, entities=entities,
                                  me=args["me"], reportedBy=convMeta["reportedBy"])
                    yield db.batch_insert(convId, "items", {"meta": convReport})

        args.update({"entities": entities, "ownerId": convOwnerId,
                     "convId": convId})

        # Update New Report comment Details
        commentId = utils.getUniqueKey()
        timeUUID = uuid.uuid1().bytes
        meta = {"owner": myId, "parent": reportId, "comment": comment,
                "timestamp": str(int(time.time())),
                "uuid": timeUUID, "richText": str(False)}
        if snippet:
            meta['snippet'] = snippet

        yield db.batch_insert(commentId, "items", {'meta': meta})

        # Update list of comments for this report
        yield db.insert(reportId, "itemResponses",
                        "%s:%s:%s" % (myId, commentId, action), timeUUID)

        yield self._renderReportResponses(request, convId, convMeta, args)
        request.write("$('#report-comment').attr('value', '')")

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self.renderItem(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == "responses":
                d = self._responses(request)
            if action == "likes":
                d = self._likes(request)
            #if action == "report":
            #    d = self._renderReport(request)
            #if action == "showReportDialog":
            #    d = self._renderReportDialog(request)

        return self._epilogue(request, d)

    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1:
            action = request.postpath[0]
            availableActions = ["new", "comment", "tag", "untag", "like",
                                "unlike", "remove", "delete"]
            if action in availableActions:
                d = getattr(self, "_" + request.postpath[0])(request)
        #if segmentCount == 2 and request.postpath[0] == "report":
        #    action = request.postpath[1]
        #    availableReportActions = ["report", "repost", "accept", "reject"]
        #    if action in availableReportActions:
        #        d = self._submitReport(request, action)

        return self._epilogue(request, d)


#
# RESTful API for managing items.
#
class APIItemResource(base.APIBaseResource):

    @defer.inlineCallbacks
    def _newItem(self, request):
        token = self._ensureAccessScope(request, 'post-item')
        authInfo = utils.AuthInfo()
        authInfo.username = token.user
        authInfo.organization = token.org
        convType = 'status'

        convId, conv, keywords = yield Item.new(request, authInfo, convType, richText=True)
        if keywords:
            raise errors.InvalidRequest(_('Matching keywords found(%s). Set reportOK=1.') % ', '.join(keywords))
        else:
            self._success(request, 201, {'id': convId})

    @defer.inlineCallbacks
    def _newComment(self, request):
        token = self._ensureAccessScope(request, 'post-item')
        convId = request.postpath[0]
        orgId = token.org
        userId = token.user
        convId, conv = yield utils.getValidItemId(request, '', itemId=convId,  myOrgId=orgId, myId=userId)

        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                                constants.COMMENT_PREVIEW_LENGTH,
                                                richText=True)
        review = int(utils.getRequestArg(request, '_review') or '0')

        itemId, convId, items, keywords = yield Item._comment(convId, conv,
                                                    comment, snippet, userId,
                                                    orgId, True, review)
        if keywords:
            raise errors.InvalidRequest(_('Matching keywords found(%s). Set reportOK=1.') % ', '.join(keywords))
        else:
            self._success(request, 201, {'id': itemId})

    def render_POST(self, request):
        apiAccessToken = request.apiAccessToken
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._newItem(request)
        if segmentCount == 3 and request.postpath[1] == 'comments' and not request.postpath[2]:
            d = self._newComment(request)

        return self._epilogue(request, d)
