import json
import uuid
import time

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, Db, utils, feed, plugins, constants, tags, fts
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock



class ItemResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def renderItem(self, request, toFeed=False):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        convId = utils.getRequestArg(request, "id")
        if not convId:
            raise errors.MissingParam()

        conv = yield Db.get_slice(convId, "items", ['meta', 'tags'])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.InvalidRequest()
        itemType = conv["meta"].get("type", None)

        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        if script and landing:
            yield render(request, "item.mako", **args)

        args['convId'] = convId
        args['items'] = {convId: conv}
        meta = conv["meta"]
        owner = meta["owner"]

        relation = Relation(myKey, [])
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initSubscriptionsList(),
                                  relation.initPendingList(),
                                  relation.initFollowersList()])

        if not utils.checkAcl(myKey, meta["acl"], owner,
                             relation, myOrgId, meta["aclIds"]):
            defer.returnValue(None)

        if script and appchange:
            yield renderScriptBlock(request, "item.mako", "layout",
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
            toFetchEntities.add(conv['meta']['target'])

        entities = yield Db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        args["entities"].update(entities)

        renderers = []

        if script:
            if plugin:
                args['toFeed'] = toFeed
                d =  plugin.renderRoot(request, convId, args)
                del args['toFeed']
            else:
                d = renderScriptBlock(request, "item.mako", "conv_root",
                        landing, "#conv-root-%s > .conv-summary" %(convId),
                        "set", **args)
            renderers.append(d)

        convOwner = args["items"][convId]["meta"]["owner"]
        if convOwner not in args["entities"]:
            owner = yield Db.get(convOwner, "entities", super_column="basic")
            owner = utils.supercolumnsToDict([owner])
            args.update({"entities": {convOwner: owner}})

        args["ownerId"] = convOwner

        if script:
            d = renderScriptBlock(request, "item.mako", "conv_owner", landing,
                                  "#conv-avatar-%s" % convId, "set", **args)
            renderers.append(d)

        # A copy of this code for fetching comments is present in _responses
        # Most changes here may need to be done there too.
        itemResponses = yield Db.get_slice(convId, "itemResponses",
                                           start=start, reverse=True,
                                           count=constants.COMMENTS_PER_PAGE+1)
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

        d1 = Db.multiget_slice(toFetchEntities, "entities", ["basic"])
        d2 = Db.multiget_slice(responseKeys, "items", ["meta"])
        d3 = Db.multiget_slice(responseKeys + [convId], "itemLikes", [myKey])
        d4 = Db.get_slice(myOrgId, "orgTags", toFetchTags)\
                                    if toFetchTags else defer.succeed([])

        fetchedEntities = yield d1
        fetchedItems = yield d2
        myLikes = yield d3
        fetchedTags = yield d4

        args["items"].update(utils.multiSuperColumnsToDict(fetchedItems))
        args["entities"].update(utils.multiSuperColumnsToDict(fetchedEntities))
        args["myLikes"] = utils.multiColumnsToDict(myLikes)
        args["tags"] = utils.supercolumnsToDict(fetchedTags)
        args["responses"] = {convId: responseKeys}
        if nextPageStart:
            args["oldest"] = utils.encodeKey(nextPageStart)

        if script:
            d = renderScriptBlock(request, "item.mako", 'item_footer',
                                  landing, '#item-footer-%s' % convId,
                                  'set', args=[convId], **args)
            renderers.append(d)
            d = renderScriptBlock(request, "item.mako", 'conv_tags',
                                  landing, '#conv-tags-wrapper-%s' % convId,
                                  'set', **args)
            renderers.append(d)
            d = renderScriptBlock(request, "item.mako", 'conv_comments',
                                  landing, '#conv-comments-wrapper-%s' % convId,
                                  'set', **args)
            renderers.append(d)
            d = renderScriptBlock(request, "item.mako", 'conv_comment_form',
                                  landing, '#comment-form-wrapper-%s' % convId,
                                  'set', **args)
            renderers.append(d)

        # Wait till the item is fully rendered.
        if renderers:
            yield defer.DeferredList(renderers)

        # TODO: Render other blocks

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "item.mako", **args)


    @defer.inlineCallbacks
    def createItem(self, request):
        convType = utils.getRequestArg(request, "type")
        myKey = request.getSession(IAuthInfo).username

        parent = None
        convOwner = myKey
        responseType = 'I'

        if convType in plugins:
            plugin = plugins[convType]
            convId, conv = yield plugin.create(request)
            timeUUID = conv["meta"]["uuid"]
            convACL = conv["meta"]["acl"]

            request.args["id"] = [convId]
            commentSnippet = ""
            userItemValue = ":".join([responseType, convId, convId, convType,
                                      myKey, commentSnippet])

            deferreds = []
            d = feed.pushToFeed(myKey, timeUUID, convId, parent,
                                responseType, convType, convOwner, myKey)
            deferreds.append(d)

            d = feed.pushToOthersFeed(myKey, timeUUID, convId,
                                      parent, convACL, responseType,
                                      convType, convOwner)
            deferreds.append(d)

            d = Db.insert(myKey, "userItems", userItemValue, timeUUID)
            deferreds.append(d)

            if plugins[convType].hasIndex:
                d = Db.insert(myKey, "userItems_%s"%(convType),
                              userItemValue, timeUUID)
                deferreds.append(d)

            deferredList = defer.DeferredList(deferreds)
            yield deferredList

            toFeed = True if convType in ['status', 'poll', 'event'] else False
            yield self.renderItem(request, toFeed)

            yield renderScriptBlock(request, 'feed.mako', 'share_status',
                                    False, "#sharebar", "set", True,
                                    handlers={"onload": "$('#sharebar-links .selected').removeClass('selected'); $('#sharebar-link-status').addClass('selected');"})


    @defer.inlineCallbacks
    def _like(self, request):
        itemId = utils.getRequestArg(request, "id")
        myId = request.getSession(IAuthInfo).username

        # Check if I already liked the item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
            raise errors.InvalidRequest()
        except ttypes.NotFoundException:
            pass

        # Get the item and the conversation
        item = yield Db.get(itemId, "items", super_column="meta")
        item = utils.supercolumnsToDict([item])

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield Db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
            commentSnippet = utils.toSnippet(item["meta"].get("comment"))
        else:
            convId = itemId
            conv = item
            commentSnippet = ""

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # TODO: Check if I have access to that item before liking it!

        # Update the likes count
        likesCount = int(item["meta"].get("likesCount", "0"))
        if likesCount % 5 == 3:
            likesCount = yield Db.get_count(itemId, "itemLikes")

        yield Db.insert(itemId, "items", str(likesCount+1), "likesCount", "meta")

        timeUUID = uuid.uuid1().bytes
        responseType = "L"
        # 1. add user to Likes list
        yield Db.insert(itemId, "itemLikes", timeUUID, myId)

        # 2. add user to the followers list of parent item
        yield Db.insert(convId, "items", "", myId, "followers")

        # 3. update user's feed, feedItems, feed_*

        userItemValue = ":".join([responseType, itemId, convId, convType,
                                  convOwnerId, commentSnippet])
        yield Db.insert(myId, "userItems", userItemValue, timeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield Db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

        yield feed.pushToFeed(myId, timeUUID, itemId, convId,
                              responseType, convType, convOwnerId, myId)

        # 4. update feed, feedItems, feed_* of user's followers/friends
        yield feed.pushToOthersFeed(myId, timeUUID, itemId, convId, convACL,
                                    responseType, convType, convOwnerId)

        yield notifications.pushNotifications( itemId, convId, responseType, convType,
                                    convOwnerId, myId, timeUUID)

        # Finally, update the UI
        # TODO

    @defer.inlineCallbacks
    def _unlike(self, request):
        itemId = utils.getRequestArg(request, "id")
        myId = request.getSession(IAuthInfo).username

        # Make sure that I liked this item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
            likeTimeUUID = cols.column.value
        except ttypes.NotFoundException:
            raise errors.InvalidRequest()

        # Get the item and the conversation
        item = yield Db.get(itemId, "items", super_column="meta")
        item = utils.supercolumnsToDict([item])

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield Db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
        else:
            convId = itemId
            conv = item

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # 1. remove the user from likes list.
        yield Db.remove(itemId, "itemLikes", myId)

        # Update the likes count
        likesCount = int(item.get("likesCount", "1"))
        if likesCount % 5 == 0:
            likesCount = yield Db.get_count(itemId, "itemLikes")
        yield Db.insert(itemId, "items", str(likesCount -1), "likesCount", "meta")

        responseType = 'L'
        # 2. Don't remove the user from followers list
        #    (use can also become follower by responding to item,
        #        so user can't be removed from followers list)

        # 3. delete from user's feed, feedItems, feed_*
        yield feed.deleteFromFeed(myId, itemId, convId,
                                  convType, myId, responseType)

        # 4. delete from feed, feedItems, feed_* of user's friends/followers
        yield feed.deleteFromOthersFeed(myId, itemId, convId, convType,
                                        convACL, convOwnerId, responseType)

        # FIX: if user updates more than one item at exactly same time,
        #      one of the updates will overwrite the other. Fix it.
        yield Db.remove(myId, "userItems", likeTimeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield Db.remove(myId, "userItems_"+ convType, likeTimeUUID)

        yield notifications.deleteNofitications(convId, likeTimeUUID)

        # Finally, update the UI
        # TODO

    @defer.inlineCallbacks
    def _comment(self, request):
        myId = request.getSession(IAuthInfo).username
        convId = utils.getRequestArg(request, "parent")
        comment = utils.getRequestArg(request, "comment")
        if not convId or not comment:
            raise errors.MissingParam()

        # 0. Fetch conversation and see if I have access to it.
        # TODO: Check ACL
        conv = yield Db.get_slice(convId, 'items', super_column='meta')
        conv = utils.columnsToDict(conv)
        convType = conv.get("type", "status")

        # 1. Create and add new item
        timeUUID = uuid.uuid1().bytes
        meta = {"owner": myId, "parent": convId, "comment": comment,
                "timestamp": str(int(time.time())), "uuid": timeUUID}
        followers = {myId: ''}
        itemId = utils.getUniqueKey()
        yield Db.batch_insert(itemId, "items", {'meta': meta,
                                                'followers': followers})

        # 2. Update response count and add myself to the followers of conv
        convOwnerId = conv["owner"]
        convType = conv["type"]
        responseCount = int(conv.get("responseCount", "0"))
        if responseCount % 5 == 3:
            responseCount = yield Db.get_count(convId, "itemResponses")

        convUpdates = {"responseCount": str(responseCount + 1)}
        yield Db.batch_insert(convId, "items", {"meta": convUpdates,
                                                "followers": followers})

        # 3. Add item as response to parent

        yield Db.insert(convId, "itemResponses",
                        "%s:%s" % (myId, itemId), timeUUID)

        # 4. Update userItems and userItems_*
        responseType = "C"
        commentSnippet = utils.toSnippet(comment)
        userItemValue = ":".join([responseType, itemId, convId, convType,
                                  convOwnerId, commentSnippet])
        yield Db.insert(myId, "userItems", userItemValue, timeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield Db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

        # 5. Update my feed.
        yield feed.pushToFeed(myId, timeUUID, itemId, convId, responseType,
                              convType, convOwnerId, myId)

        # 6. Push to other's feeds
        convACL = conv.get("acl", "company")
        yield feed.pushToOthersFeed(myId, timeUUID, itemId, convId, convACL,
                                    responseType, convType, convOwnerId)

        yield notifications.pushNotifications( itemId, convId, responseType,
                                              convType, convOwnerId, myId, timeUUID)
        # Finally, update the UI
        numShowing = utils.getRequestArg(request, "nc") or "0"
        numShowing = int(numShowing) + 1
        isFeed = False if request.getCookie("_page") == "item" else True
        yield renderScriptBlock(request, 'item.mako', 'conv_comments_head',
                        False, '#comments-header-%s' % (convId), 'set',
                        args=[convId, responseCount, numShowing, isFeed])

        entities = yield Db.get(myId, "entities", super_column="basic")
        entities = {myId: utils.supercolumnsToDict([entities])}
        items = {itemId: {"meta": meta}}
        data = {"entities": entities, "items": items}
        yield renderScriptBlock(request, 'item.mako', 'conv_comment', False,
                                '#comments-%s' % convId, 'append', True,
                                handlers={"onload": "$(':text', '#comment-form-%s').val(''); $('[name=\"nc\"]', '#comment-form-%s').val('%s')" % (convId, convId, numShowing)},
                                args=[convId, itemId], **data)
        d = fts.solr.updateIndex(itemId, {'meta':meta})


    @defer.inlineCallbacks
    def _likes(self, request):
        pass

    @defer.inlineCallbacks
    def _responses(self, request):
        convId = utils.getRequestArg(request, "id")
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        # A copy of this code for fetching comments is present in renderItem
        # Most changes here may need to be done there too.
        toFetchEntities = set()
        itemResponses = yield Db.get_slice(convId, "itemResponses",
                                           start=start, reverse=True,
                                           count=constants.COMMENTS_PER_PAGE+1)

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

        d3 = Db.multiget_slice(responseKeys + [convId], "itemLikes")
        d2 = Db.multiget_slice(responseKeys + [convId], "items", ["meta"])
        d1 = Db.multiget_slice(toFetchEntities, "entities", ["basic"])

        fetchedItems = yield d2
        fetchedEntities = yield d1
        myLikes = yield d3

        isFeed = False if request.getCookie("_page") == "item" else True
        args = {"convId": convId, "isFeed": isFeed, "items":{}, "entities": {}}
        args["items"].update(utils.multiSuperColumnsToDict(fetchedItems))
        args["entities"].update(utils.multiSuperColumnsToDict(fetchedEntities))
        args["myLikes"] = utils.multiColumnsToDict(myLikes)
        args["responses"] = {convId: responseKeys}
        if nextPageStart:
            args["oldest"] = utils.encodeKey(nextPageStart)

        if isFeed:
            yield renderScriptBlock(request, "item.mako", 'conv_comments',
                        not self._ajax, '#conv-comments-wrapper-%s' % convId,
                        'set', **args)
        else:
            landing = not self._ajax
            showing = utils.getRequestArg(request, "nc") or "0"
            showing = int(showing) + len(responseKeys)
            args["showing"] = showing
            args["total"] = int(args["items"][convId]["meta"].get("responseCount", "0"))

            yield renderScriptBlock(request, "item.mako", 'conv_comments_head',
                                    landing, '#comments-header-%s' % convId,
                                    'set', **args)
            yield renderScriptBlock(request, "item.mako", 'conv_comments_only',
                            landing, '#comments-%s' % convId, 'prepend', True,
                            handlers={"onload": "$('[name=\"nc\"]', '#comment-form-%s').val('%s')" % (convId, showing)},
                            **args)


    @defer.inlineCallbacks
    def _tag(self, request):
        tagName = utils.getRequestArg(request, "tag")
        if not tagName:
            raise errors.MissingParam()

        (itemId, item) = yield utils.getValidItemId(request, "id", ["tags"])
        if "parent" in item["meta"]:
            raise errors.InvalidRequest()

        (tagId, tag) = yield tags.ensureTag(request, tagName)
        if tagId in item.get("tags", {}):
            raise errors.InvalidRequest() # Tag already exists on item.

        d1 = Db.insert(itemId, "items", '', tagId, "tags")
        d2 = Db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])

        orgId = request.getSession(IAuthInfo).organization
        tagItemsCount = int(tag.get("itemsCount", "0")) + 1
        if tagItemsCount % 10 == 7:
            tagItemsCount = yield Db.get_count(tagId, "tagItems") + 1
        Db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)

        yield defer.DeferredList([d1, d2])
        yield renderScriptBlock(request, "item.mako", 'conv_tag', False,
                                '#conv-tags-%s'%itemId, "append", True,
                                handlers={"onload": "$('input:text', '#addtag-form-%s').val('');" % itemId},
                                args=[itemId, tagId, tag["title"]])


    @defer.inlineCallbacks
    def _untag(self, request):
        tagId = utils.getRequestArg(request, "tag")
        if not tagId:
            raise errors.MissingParam()

        (itemId, item) = yield utils.getValidItemId(request, "id", ["tags"])
        if "parent" in item:
            raise errors.InvalidRequest()

        if tagId not in item.get("tags", {}):
            raise errors.InvalidRequest()  # No such tag on item

        d1 = Db.remove(itemId, "items", tagId, "tags")
        d2 = Db.remove(tagId, "tagItems", item["meta"]["uuid"])

        orgId = request.getSession(IAuthInfo).organization
        try:
            itemsCountCol = yield Db.get(orgId, "orgTags", "itemsCount", tagId)
            tagItemsCount = int(itemsCountCol.column.value) - 1
            if tagItemsCount % 10 == 7:
                tagItemsCount = yield Db.get_count(tagId, "tagItems") - 1
            Db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)
        except ttypes.NotFoundException:
            pass
        yield defer.DeferredList([d1, d2])


    def _tags(self, request):
        pass


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d =  self.renderItem(request)
        elif segmentCount == 1:
            path = request.postpath[0]
            if path == "responses":
                d = self._responses(request)
            if path == "likes":
                d = self._likes(request)
            elif path == 'like' :
                d = self._like(request)
            elif path == 'unlike':
                d = self._unlike(request)
            elif path == 'untag':
                d = self._untag(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1:
            path = request.postpath[0]
            if path == 'new':
                d =  self.createItem(request)
            elif path == 'comment':
                d = self._comment(request)
            elif path == 'tag':
                d = self._tag(request)
            elif path == 'untag':
                d = self._untag(request)

        return self._epilogue(request, d)
