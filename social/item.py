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
from social.logging      import profile, dump_args



class ItemResource(base.BaseResource):
    isLeaf = True


    @profile
    @defer.inlineCallbacks
    @dump_args
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


    @profile
    @defer.inlineCallbacks
    @dump_args
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

            commentSnippet = ""
            userItemValue = ":".join([responseType, convId, convId,
                                      convType, myKey, commentSnippet])

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

            cols = yield Db.get_slice(myKey, "entities", ["basic"])
            me = utils.supercolumnsToDict(cols)

            deferredList = defer.DeferredList(deferreds)
            yield deferredList

            data = {"items":{convId:conv},
                    "entities":{myKey: me}, "script": True}
            d1 = renderScriptBlock(request, "item.mako", "item_layout",
                                   False, "#user-feed", "prepend",
                                   args=[convId, True, True], **data)

            defaultType = plugins.keys()[0]
            d2 = plugins[defaultType].renderShareBlock(request, True)

            yield defer.DeferredList([d1, d2])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _like(self, request):

        myId = request.getSession(IAuthInfo).username

        # Get the item and the conversation
        (itemId, item) = yield utils.getValidItemId(request, "id")

        # Check if I already liked the item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
            raise errors.InvalidRequest()
        except ttypes.NotFoundException:
            pass

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



    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unlike(self, request):

        myId = request.getSession(IAuthInfo).username

        # Get the item and the conversation
        (itemId, item) = yield utils.getValidItemId(request, "id", ["tags"])
        # Make sure that I liked this item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
            likeTimeUUID = cols.column.value
        except ttypes.NotFoundException:
            raise errors.InvalidRequest()



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


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _comment(self, request):
        myId = request.getSession(IAuthInfo).username
        comment = utils.getRequestArg(request, "comment")
        if not comment:
            raise errors.MissingParam()

        # 0. Fetch conversation and see if I have access to it.
        # TODO: Check ACL

        (convId, conv) = yield utils.getValidItemId(request, "parent")
        convType = conv["meta"].get("type", "status")

        # 1. Create and add new item
        timeUUID = uuid.uuid1().bytes
        meta = {"owner": myId, "parent": convId, "comment": comment,
                "timestamp": str(int(time.time())), "uuid": timeUUID}
        followers = {myId: ''}
        itemId = utils.getUniqueKey()
        yield Db.batch_insert(itemId, "items", {'meta': meta,
                                                'followers': followers})

        # 2. Update response count and add myself to the followers of conv
        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        responseCount = int(conv["meta"].get("responseCount", "0"))
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
        convACL = conv["meta"].get("acl", "company")
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
                                handlers={"onload": "(function(){$('.comment-input', '#comment-form-%s').val(''); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, convId, numShowing)},
                                args=[convId, itemId], **data)
        d = fts.solr.updateIndex(itemId, {'meta':meta})

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _likes(self, request):
        pass


    @profile
    @defer.inlineCallbacks
    @dump_args
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
                            handlers={"onload": "(function(){$('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, showing)},
                            **args)



    @profile
    @defer.inlineCallbacks
    @dump_args
    def _tag(self, request):
        tagName = utils.getRequestArg(request, "tag")
        myId = request.getSession(IAuthInfo).username

        if not tagName:
            raise errors.MissingParam()

        (itemId, item) = yield utils.getValidItemId(request, "id", ["tags"])
        if "parent" in item["meta"]:
            raise errors.InvalidRequest()

        (tagId, tag) = yield tags.ensureTag(request, tagName)
        if tagId in item.get("tags", {}):
            raise errors.InvalidRequest() # Tag already exists on item.

        d1 = Db.insert(itemId, "items", myId, tagId, "tags")
        d2 = Db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])
        d3 = Db.get_slice(tagId, "tagFollowers")

        orgId = request.getSession(IAuthInfo).organization
        tagItemsCount = int(tag.get("itemsCount", "0")) + 1
        if tagItemsCount % 10 == 7:
            tagItemsCount = yield Db.get_count(tagId, "tagItems") + 1
        Db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)

        result = yield defer.DeferredList([d1, d2, d3])
        followers = utils.columnsToDict(result[2][1]).keys()
        yield renderScriptBlock(request, "item.mako", 'conv_tag', False,
                                '#conv-tags-%s'%itemId, "append", True,
                                handlers={"onload": "(function(){$('input:text', '#addtag-form-%s').val('');})();" % itemId},
                                args=[itemId, tagId, tag["title"]])

        convACL = item["meta"]["acl"]
        convType = item["meta"]["type"]
        timeUUID = uuid.uuid1().bytes
        convOwnerId = item["meta"]["owner"]
        responseType = "T"

        yield feed.pushToFeed(myId, timeUUID, itemId, itemId, responseType,
                              convType, convOwnerId, myId, tagId=tagId)

        if followers:
            yield feed.pushToOthersFeed(myId, timeUUID, itemId, itemId, convACL,
                                        responseType, convType, convOwnerId,
                                        others=followers, tagId=tagId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _untag(self, request):
        tagId = utils.getRequestArg(request, "tag")
        myId = request.getSession(IAuthInfo).username
        if not tagId:
            raise errors.MissingParam()

        (itemId, item) = yield utils.getValidItemId(request, "id", ["tags"])
        if "parent" in item:
            raise errors.InvalidRequest()

        if tagId not in item.get("tags", {}):
            raise errors.InvalidRequest()  # No such tag on item

        d1 = Db.remove(itemId, "items", tagId, "tags")
        d2 = Db.remove(tagId, "tagItems", item["meta"]["uuid"])
        d3 = Db.get_slice(tagId, "tagFollowers")

        orgId = request.getSession(IAuthInfo).organization
        try:
            itemsCountCol = yield Db.get(orgId, "orgTags", "itemsCount", tagId)
            tagItemsCount = int(itemsCountCol.column.value) - 1
            if tagItemsCount % 10 == 7:
                tagItemsCount = yield Db.get_count(tagId, "tagItems") - 1
            Db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)
        except ttypes.NotFoundException:
            pass
        result = yield defer.DeferredList([d1, d2, d3])
        followers = utils.columnsToDict(result[2][1]).keys()

        convId = itemId
        convACL = item["meta"]["acl"]
        convType = item["meta"]["type"]
        convOwnerId = item["meta"]["owner"]
        responseType = 'T'

        yield feed.deleteFromFeed(myId, itemId, convId, convType,
                                  myId, responseType, tagId= tagId)

        if followers:
            yield feed.deleteFromOthersFeed(myId, itemId, convId, convType,
                                            convACL, convOwnerId, responseType,
                                            others=followers, tagId=tagId)

    @defer.inlineCallbacks
    def _delete(self, request):

        #TODO: refactor "delete item likes"

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        conv = None

        (itemId, item) = yield utils.getValidItemId(request, 'id', ["tags"])
        convId = item["meta"].get("parent", itemId)
        itemOwner = item["meta"]["owner"]

        if itemId == convId:
            conv = item
        else:
            conv = yield Db.get_slice(convId, "items", ["meta"])
            conv = utils.supercolumnsToDict(conv)

        if itemOwner != myId and (itemId != convId and not conv):
            raise errors.InvalidRequest()

        if itemOwner != myId and \
            (itemId == convId or conv["meta"]["owner"] != myId):
            raise errors.UnAuthorised()

        itemType = item["meta"].get("type", None)
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]
        convOwnerId = conv["meta"]["owner"]

        #mark the item as deleted.
        yield Db.insert(itemId, "items", '', 'deleted', 'meta')
        yield Db.insert(itemOwner, "deletedConvs", '', convId)

        #TODO: custom data to be deleted by plugins
        #if itemType and itemType in plugins:
        #    yield plugins[itemType].delete(itemId)

        #if the item is tagged remove the itemId from the tagItems and delete
        # the feed entry corresponding to tag
        responseType="T"
        if convId == itemId:
            for tagId in item.get("tags", {}):
                userId = item["tags"][tagId]
                yield Db.remove(tagId, "tagItems", item["meta"]["uuid"])
                yield feed.deleteFromFeed(userId, itemId, convId, convType,
                                          userId, responseType, tagId= tagId)
                followers = yield Db.get_slice(tagId, "tagFollowers")
                followers = utils.columnsToDict(followers).keys()
                if followers:
                    yield feed.deleteFromOthersFeed(myId, itemId, convId, convType,
                                                   convACL, convOwnerId, responseType,
                                                   others=followers, tagId=tagId)

        #remove from itemLikes
        itemResponses = yield Db.get_slice(convId, "itemResponses")
        itemResponses = utils.columnsToDict(itemResponses)
        itemLikes = yield Db.get_slice(itemId, "itemLikes")
        itemLikes = utils.columnsToDict(itemLikes)
        responseType = "L"
        for userId in itemLikes:
            tuuid = itemLikes[userId]
            yield Db.remove(userId, "userItems", tuuid)
            if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                yield Db.remove(userId, "userItems_"+ itemType, tuuid)
            yield feed.deleteFromFeed(userId, itemId, convId, convType,
                                      userId, responseType)
            yield feed.deleteFromOthersFeed(userId, itemId, convId, convType,
                                            convACL, convOwnerId, responseType)

        # if conv is being deleted, delete feed corresponding to commentLikes also.
        if itemId == convId:
            for tuuid in itemResponses:
                userId, responseId = itemResponses[tuuid].split(":")
                itemLikes = yield Db.get_slice(responseId, "itemLikes")
                itemLikes = utils.columnsToDict(itemLikes)
                for userId in itemLikes:
                    tuuid = itemLikes[userId]
                    yield Db.remove(userId, "userItems", tuuid)
                    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                        yield Db.remove(userId, "userItems_"+ itemType, tuuid)
                    yield feed.deleteFromFeed(userId, responseId, convId, convType,
                                              userId, responseType)
                    yield feed.deleteFromOthersFeed(userId, responseId, convId, convType,
                                                    convACL, convOwnerId, responseType)

        #remove from itemResponses
        responseType = "C"
        for tuuid in itemResponses:
            userId, responseId = itemResponses[tuuid].split(":")
            if itemId == convId or (responseId == itemId):
                deleteFromFeed = (itemId == convId)
                yield Db.remove(userId, "userItems", tuuid)
                if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                    yield Db.remove(userId, "userItems_"+ itemType, tuuid)
                yield feed.deleteFromFeed(userId, responseId, convId, convType,
                                          userId, responseType)
                yield feed.deleteFromOthersFeed(userId, responseId, convId,
                                                convType, convACL, convOwnerId,
                                                responseType)
                yield Db.insert(convId, "deletedConvs", '', responseId)
                yield Db.remove(convId, "itemResponses", tuuid)
                #delete notifications
        #update itemResponse Count
        responseCount = yield Db.get_count(convId, "itemResponses")
        yield Db.insert(convId, "items", str(responseCount), "responseCount", "meta")

        if itemId == convId:
            responseType="I"
            yield Db.remove(conv["meta"]['owner'], "userItems", conv["meta"]["uuid"])
            yield feed.deleteFromFeed(convOwnerId, convId, convId, convType,
                                      itemOwner, responseType)
            yield feed.deleteFromOthersFeed(convOwnerId, convId, convId,
                                            convType, convACL, convOwnerId,
                                            responseType, None)
        #TODO: delete notifications



    def _tags(self, request):
        pass

    @profile
    @dump_args
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
            elif path == "tag":
                d = self._tag(request)
            elif path == 'delete':
                d = self._delete(request)

        return self._epilogue(request, d)

    @profile
    @dump_args
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
            elif path == 'delete':
                d = self._delete(request)

        return self._epilogue(request, d)
