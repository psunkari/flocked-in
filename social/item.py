import json
import uuid
import time


from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, db, utils, feed
from social             import plugins, constants, tags, fts
from social             import notifications, _, errors
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging      import profile, dump_args


@defer.inlineCallbacks
def pushNotifications(notifyType, convId, convType, convOwner,
                          actor, timeUUID, followers=None):
    notifyId = ":".join([convId, convType, convOwner, notifyType])
    if not followers:
        followers = yield db.get_slice(convId, "items", super_column="followers")
    deferreds = []

    for follower in followers:
        userKey = follower.column.name
        if actor != userKey:
            d0 = db.get_slice(userKey, "notificationItems", super_column=notifyId, count=1, reverse=True)
            d0.addCallback(lambda x: db.remove(userKey, "notifications", x[0].column.name) if (x and x[0].column.name != timeUUID) else defer.succeed([]))
            d1 = db.insert(userKey, "notifications", notifyId, timeUUID)
            d2 = db.insert(userKey, "latest", notifyId, timeUUID, "notifications")
            d3 = db.batch_insert(userKey, "notificationItems", {notifyId:{timeUUID:actor}})
            deferreds.extend([d0, d1, d2, d3])
    yield defer.DeferredList(deferreds)


class ItemResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def renderItem(self, request, toFeed=False):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        convId, conv = yield utils.getValidItemId(request, "id", columns=['tags'])
        itemType = conv["meta"].get("type", None)

        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        args['convId'] = convId
        args['items'] = {convId: conv}
        meta = conv["meta"]
        owner = meta["owner"]

        if script and landing:
            yield render(request, "item.mako", **args)

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

        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
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
            owner = yield db.get(convOwner, "entities", super_column="basic")
            owner = utils.supercolumnsToDict([owner])
            args.update({"entities": {convOwner: owner}})

        args["ownerId"] = convOwner

        if script:
            if itemType != "feedback":
                d = renderScriptBlock(request, "item.mako", "conv_owner",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", **args)
            else:
                feedbackType = conv['meta']['subType']
                d = renderScriptBlock(request, "item.mako", "feedback_icon",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", args=[feedbackType])

            renderers.append(d)

        # A copy of this code for fetching comments is present in _responses
        # Most changes here may need to be done there too.
        itemResponses = yield db.get_slice(convId, "itemResponses",
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

        relation = Relation(myKey, [])
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initSubscriptionsList()])
        friends_subscriptions = relation.friends.keys() + list(relation.subscriptions)
        likes = yield db.get_slice(convId, "itemLikes", friends_subscriptions) \
                            if friends_subscriptions else defer.succeed([])
        toFetchEntities.update([x.column.name for x in likes])
        d1 = db.multiget_slice(toFetchEntities, "entities", ["basic"])
        d2 = db.multiget_slice(responseKeys, "items", ["meta"])
        d3 = db.multiget_slice(responseKeys + [convId], "itemLikes", [myKey])
        d4 = db.get_slice(myOrgId, "orgTags", toFetchTags)\
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
            d = renderScriptBlock(request, "item.mako", 'conv_footer',
                                  landing, '#item-footer-%s' % convId,
                                  'set', **args)
            renderers.append(d)

            d = renderScriptBlock(request, "item.mako", 'conv_tags',
                        landing, '#conv-tags-wrapper-%s' % convId, 'set',
                        handlers={"onload":"$('#conv-meta-wrapper-%s').removeClass('no-tags')"%convId} if toFetchTags else None, **args)
            renderers.append(d)

            d = renderScriptBlock(request, "item.mako", 'conv_comments',
                        landing, '#conv-comments-wrapper-%s' % convId, 'set', **args)
            renderers.append(d)

            d = renderScriptBlock(request, "item.mako", 'conv_comment_form',
                        landing, '#comment-form-wrapper-%s' % convId, 'set',
                        True, handlers={"onload": "(function(obj){$$.convs.load(obj);})(this);"}, **args)
            renderers.append(d)

            numLikes = int(conv["meta"].get("likesCount", "0"))
            if numLikes:
                numLikes = int(conv["meta"].get("likesCount", "0"))
                iLike = myKey in args["myLikes"].get(convId, [])
                d = renderScriptBlock(request, "item.mako", 'conv_likes',
                            landing, '#conv-likes-wrapper-%s' % convId, 'set',
                            args=[convId, numLikes, iLike, [x.column.name for x in likes]],
                            entities= args['entities'])
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
    def _new(self, request):
        convType = utils.getRequestArg(request, "type")
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        parent = None
        convOwner = myId
        responseType = 'I'

        if convType in plugins:
            plugin = plugins[convType]
            convId, conv = yield plugin.create(request)
            timeUUID = conv["meta"]["uuid"]
            convACL = conv["meta"]["acl"]

            commentSnippet = ""
            userItemValue = ":".join([responseType, convId, convId,
                                      convType, myId, commentSnippet])

            deferreds = []
            d = feed.pushToFeed(myId, timeUUID, convId, parent,
                                responseType, convType, convOwner, myId)
            deferreds.append(d)

            d = feed.pushToOthersFeed(myId, timeUUID, convId,
                                      parent, convACL, responseType,
                                      convType, convOwner)
            deferreds.append(d)

            d = db.insert(myId, "userItems", userItemValue, timeUUID)
            deferreds.append(d)

            if plugins[convType].hasIndex:
                d = db.insert(myId, "userItems_%s"%(convType),
                              userItemValue, timeUUID)
                deferreds.append(d)


            deferredList = defer.DeferredList(deferreds)
            yield deferredList

            data = {"items":{convId:conv},
                    "entities":{myId: args['me']}, "script": True}
            args.update(data)
            onload = "(function(obj){$$.convs.load(obj);})(this);$('#attached-files').empty()"
            d1 = renderScriptBlock(request, "item.mako", "item_layout",
                            False, "#user-feed", "prepend", args=[convId, 'conv-item-created'],
                            handlers={"onload":onload}, **args)

            defaultType = plugins.keys()[0]
            d2 = plugins[defaultType].renderShareBlock(request, True)

            yield defer.DeferredList([d1, d2])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _like(self, request):
        myId = request.getSession(IAuthInfo).username
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        # Get the item and the conversation
        (itemId, item) = yield utils.getValidItemId(request, "id")
        extraEntities = [item["meta"]["owner"]]

        # Check if I already liked the item
        try:
            cols = yield db.get(itemId, "itemLikes", myId)
            defer.returnValue(None)     # Ignore the request if we already liked it.
        except ttypes.NotFoundException:
            pass

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
            commentSnippet = utils.toSnippet(item["meta"].get("comment"))
        else:
            convId = itemId
            conv = item
            commentSnippet = ""

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # Update the likes count
        likesCount = int(item["meta"].get("likesCount", "0"))
        if likesCount % 5 == 3:
            likesCount = yield db.get_count(itemId, "itemLikes")

        yield db.insert(itemId, "items", str(likesCount+1), "likesCount", "meta")

        timeUUID = uuid.uuid1().bytes
        responseType = "L"

        # 1. add user to Likes list
        yield db.insert(itemId, "itemLikes", timeUUID, myId)

        # 2. add user to the followers list of parent item
        yield db.insert(convId, "items", "", myId, "followers")

        # 3. update user's feed, feedItems, feed_*
        userItemValue = ":".join([responseType, itemId, convId, convType,
                                  convOwnerId, commentSnippet])
        yield db.insert(myId, "userItems", userItemValue, timeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

        yield feed.pushToFeed(myId, timeUUID, itemId, convId, responseType,
                              convType, convOwnerId, myId, entities=extraEntities)

        # 4. update feed, feedItems, feed_* of user's followers/friends
        yield feed.pushToOthersFeed(myId, timeUUID, itemId, convId, convACL,
                                    responseType, convType, convOwnerId, entities=extraEntities)

        notifyType = "L" if itemId == convId else "LC"
        yield pushNotifications(notifyType, convId, convType, convOwnerId, myId, timeUUID)

        item["meta"]["likesCount"] = str(likesCount + 1)
        args["items"] = {itemId: item}
        args["myLikes"] = {itemId:[myId]}

        if itemId != convId:
            yield renderScriptBlock(request, "item.mako", "item_footer", False,
                              "#item-footer-%s"%(itemId), "set",
                              args=[itemId], **args)
        else:

            relation = Relation(myId, [])
            yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initSubscriptionsList() ])
            friends_subscriptions = relation.friends.keys() + list(relation.subscriptions)
            if friends_subscriptions:
                likes = yield db.get_slice(convId, "itemLikes", friends_subscriptions)
                likes = [x.column.name for x in likes]
            else:
                likes = []

            isFeed = (utils.getRequestArg(request, "_pg") != "/item")
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
            if toFetchEntities:
                entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
                entities = utils.multiSuperColumnsToDict(entities)
            args["entities"] = entities


            handler = {"onload":"(function(){$$.convs.showHideComponent('%s', 'likes', true)})();"%(convId)}
            yield renderScriptBlock(request, "item.mako", "conv_footer", False,
                                    "#item-footer-%s"%(itemId), "set",
                                    args=[itemId, hasComments, hasLikes], **args)
            yield renderScriptBlock(request, "item.mako", 'conv_likes', False,
                                    '#conv-likes-wrapper-%s' % convId, 'set', True,
                                    args=[itemId, likesCount+1, True, likes], handlers=handler, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unlike(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        # Get the item and the conversation
        (itemId, item) = yield utils.getValidItemId(request, "id")
        # Make sure that I liked this item
        try:
            cols = yield db.get(itemId, "itemLikes", myId)
            likeTimeUUID = cols.column.value
        except ttypes.NotFoundException:
            defer.returnValue(None)

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
        else:
            convId = itemId
            conv = item

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # 1. remove the user from likes list.
        yield db.remove(itemId, "itemLikes", myId)

        # Update the likes count
        likesCount = int(item["meta"].get("likesCount", "1"))
        if likesCount % 5 == 0:
            likesCount = yield db.get_count(itemId, "itemLikes")
        yield db.insert(itemId, "items", str(likesCount -1), "likesCount", "meta")

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
        yield db.remove(myId, "userItems", likeTimeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield db.remove(myId, "userItems_"+ convType, likeTimeUUID)

        item["meta"]["likesCount"] = likesCount -1
        args["items"] = {itemId: item}
        args["myLikes"] = {itemId:[]}

        if itemId != convId:
             yield renderScriptBlock(request, "item.mako", "item_footer", False,
                                     "#item-footer-%s"%(itemId), "set",
                                     args=[itemId], **args)
        else:
            relation = Relation(myId, [])
            yield defer.DeferredList([relation.initFriendsList(),
                                      relation.initSubscriptionsList()])

            toFetchEntities = set()
            likes = []
            friends_subscriptions = relation.friends.keys() + list(relation.subscriptions)
            if friends_subscriptions:
                likes = yield db.get_slice(convId, "itemLikes", friends_subscriptions)
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

            entities = {}
            if toFetchEntities:
                entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
                entities = utils.multiSuperColumnsToDict(entities)

            args["entities"] = entities
            log.msg(likes, entities.keys())

            handler = {"onload":"(function(){$$.convs.showHideComponent('%s', 'likes', false)})();" %(convId)} if not likes else None
            yield renderScriptBlock(request, "item.mako", "conv_footer", False,
                                    "#item-footer-%s"%(itemId), "set",
                                    args=[itemId, hasComments, likes], **args)
            yield renderScriptBlock(request, "item.mako", 'conv_likes', False,
                                    '#conv-likes-wrapper-%s' % convId, 'set', True,
                                    args=[itemId, likesCount-1, False, likes], handlers=handler, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _comment(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        comment = utils.getRequestArg(request, "comment")
        if not comment:
            raise errors.MissingParams([_("Comment")])

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
        yield db.batch_insert(itemId, "items", {'meta': meta,
                                                'followers': followers})

        # 2. Update response count and add myself to the followers of conv
        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        responseCount = int(conv["meta"].get("responseCount", "0"))
        if responseCount % 5 == 3:
            responseCount = yield db.get_count(convId, "itemResponses")

        convUpdates = {"responseCount": str(responseCount + 1)}
        yield db.batch_insert(convId, "items", {"meta": convUpdates,
                                                "followers": followers})

        # 3. Add item as response to parent
        yield db.insert(convId, "itemResponses",
                        "%s:%s" % (myId, itemId), timeUUID)

        # 4. Update userItems and userItems_*
        responseType = "Q" if convType == "question" else 'C'
        commentSnippet = utils.toSnippet(comment)
        userItemValue = ":".join([responseType, itemId, convId, convType,
                                  convOwnerId, commentSnippet])
        yield db.insert(myId, "userItems", userItemValue, timeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

        # 5. Update my feed.
        yield feed.pushToFeed(myId, timeUUID, itemId, convId, responseType,
                              convType, convOwnerId, myId)

        # 6. Push to other's feeds
        convACL = conv["meta"].get("acl", "company")
        yield feed.pushToOthersFeed(myId, timeUUID, itemId, convId, convACL,
                                    responseType, convType, convOwnerId)

        notifyType = "C"
        yield pushNotifications(notifyType, convId, convType, convOwnerId, myId, timeUUID)

        # Finally, update the UI
        entities = yield db.get(myId, "entities", super_column="basic")
        entities = {myId: utils.supercolumnsToDict([entities])}
        items = {itemId: {"meta": meta}, convId:conv}
        args.update({"entities": entities, "items": items})


        numShowing = utils.getRequestArg(request, "nc") or "0"
        numShowing = int(numShowing) + 1
        isFeed = (utils.getRequestArg(request, "_pg") != "/item")
        yield renderScriptBlock(request, 'item.mako', 'conv_comments_head',
                        False, '#comments-header-%s' % (convId), 'set',
                        args=[convId, responseCount, numShowing, isFeed], **args)


        yield renderScriptBlock(request, 'item.mako', 'conv_comment', False,
                                '#comments-%s' % convId, 'append', True,
                                handlers={"onload": "(function(){$('.comment-input', '#comment-form-%s').val(''); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, convId, numShowing)},
                                args=[convId, itemId], **args)
        fts.solr.updateIndex(itemId, {'meta':meta}, args["orgKey"])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _likes(self, request):
        itemId, item = yield utils.getValidItemId(request, "id")
        itemLikes = yield db.get_slice(itemId, "itemLikes")
        users = [col.column.name for col in itemLikes]
        if len(users) <= 0:
            raise errors.InvalidRequest(_("Currently, no one likes the choosen item"))

        entities = {}
        owner = item["meta"].get("owner")
        cols = yield db.multiget_slice(users+[owner], "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(cols)

        args = {"users": users, "entities": entities}
        itemMeta = item['meta']
        itemType = 'comment' if 'parent' in itemMeta else itemMeta.get('type')
        args['title'] = _("People who like %s's %s") %\
                          (utils.userName(owner, entities[owner]), _(itemType))

        yield renderScriptBlock(request, "item.mako", "userListDialog", False,
                                "#likes-dlg-%s"%(itemId), "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _responses(self, request):
        convId, conv = yield utils.getValidItemId(request, "id")
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        isFeed = (utils.getRequestArg(request, "_pg") != "/item")
        responseCount = int(conv["meta"].get("responseCount", "0"))

        if isFeed and responseCount > constants.MAX_COMMENTS_IN_FEED:
            request.write("$$.fetchUri('/item?id=%s');"%convId)
            return

        # A copy of this code for fetching comments is present in renderItem
        # Most changes here may need to be done there too.
        toFetchEntities = set()
        itemResponses = yield db.get_slice(convId, "itemResponses",
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

        d3 = db.multiget_slice(responseKeys + [convId], "itemLikes", [myId])
        d2 = db.multiget_slice(responseKeys + [convId], "items", ["meta"])
        d1 = db.multiget_slice(toFetchEntities, "entities", ["basic"])

        fetchedItems = yield d2
        fetchedEntities = yield d1
        myLikes = yield d3

        args.update({"convId": convId, "isFeed": isFeed, "items":{}, "entities": {}})
        args["items"].update(utils.multiSuperColumnsToDict(fetchedItems))
        args["entities"].update(utils.multiSuperColumnsToDict(fetchedEntities))
        args["myLikes"] = utils.multiColumnsToDict(myLikes)
        args["responses"] = {convId: responseKeys}
        if nextPageStart:
            args["oldest"] = utils.encodeKey(nextPageStart)

        if isFeed:
            handler = {"onload":"(function(){$$.convs.showHideComponent('%s', 'comments', true)})();"%(convId)}
            yield renderScriptBlock(request, "item.mako", 'conv_comments',
                        not self._ajax, '#conv-comments-wrapper-%s' % convId,
                        'set', True, handlers=handler, **args)
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
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        if not tagName:
            raise errors.MissingParams([_("Tag")])

        (itemId, item) = yield utils.getValidItemId(request, "id", columns=["tags"])
        if "parent" in item["meta"]:
            raise errors.InvalidRequest(_("Tag cannot be applied on a comment"))

        (tagId, tag) = yield tags.ensureTag(request, tagName)
        if tagId in item.get("tags", {}):
            raise errors.InvalidRequest(_("Tag already exists on the choosen item"))

        d1 = db.insert(itemId, "items", myId, tagId, "tags")
        d2 = db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])
        d3 = db.get_slice(tagId, "tagFollowers")

        tagItemsCount = int(tag.get("itemsCount", "0")) + 1
        if tagItemsCount % 10 == 7:
            tagItemsCount = yield db.get_count(tagId, "tagItems")
            tagItemsCount += 1
        db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)

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
        #TODO: update userFeed
        #TODO: notifications


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _untag(self, request):
        (itemId, item) = yield utils.getValidItemId(request, "id", columns=["tags"])
        if "parent" in item:
            raise errors.InvalidRequest(_("Tags cannot be applied or removed from comments"))

        (tagId, tag) = yield utils.getValidTagId(request, "tag")
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        if tagId not in item.get("tags", {}):
            raise errors.InvalidRequest(_("No such tag on the item"))  # No such tag on item

        d1 = db.remove(itemId, "items", tagId, "tags")
        d2 = db.remove(tagId, "tagItems", item["meta"]["uuid"])
        d3 = db.get_slice(tagId, "tagFollowers")

        try:
            itemsCountCol = yield db.get(orgId, "orgTags", "itemsCount", tagId)
            tagItemsCount = int(itemsCountCol.column.value) - 1
            if tagItemsCount % 10 == 7:
                tagItemsCount = yield db.get_count(tagId, "tagItems") - 1
            db.insert(orgId, "orgTags", "%s"%tagItemsCount, "itemsCount", tagId)
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
        request.write("$('#conv-tags-%s').children('[tag-id=\"%s\"]').remove();" % (convId, tagId));

    @defer.inlineCallbacks
    def _remove(self, request, deleteAll=False):

        #TODO: refactor "delete item likes"

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        conv = None

        (itemId, item) = yield utils.getValidItemId(request, 'id', columns=["tags"])
        convId = item["meta"].get("parent", itemId)
        itemOwner = item["meta"]["owner"]

        if itemId == convId:
            conv = item
        else:
            conv = yield db.get_slice(convId, "items", ["meta"])
            conv = utils.supercolumnsToDict(conv)

        if itemOwner != myId and (itemId != convId and not conv):
            raise errors.InvalidRequest(_("Conversation does not exist!"))

        # Do I own the item or if the item is a comment, do I own the conversation?
        if itemOwner != myId and \
            (itemId == convId or conv["meta"]["owner"] != myId):
            raise errors.PermissionDenied(_("You should either own the comment or conversation to remove it"))

        itemType = item["meta"].get("type", "status")
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]
        convOwnerId = conv["meta"]["owner"]

        #mark the item as deleted.
        yield db.insert(itemId, "items", '', 'deleted', 'meta')
        yield db.insert(itemOwner, "deletedConvs", '', convId)

        #TODO: custom data to be deleted by plugins
        #if itemType and itemType in plugins:
        #    yield plugins[itemType].delete(itemId)

        #if the item is tagged remove the itemId from the tagItems and delete
        # the feed entry corresponding to tag
        responseType="T"
        if convId == itemId and deleteAll:
            for tagId in item.get("tags", {}):
                userId = item["tags"][tagId]

                yield db.remove(tagId, "tagItems", item["meta"]["uuid"])
                followers = yield db.get_slice(tagId, "tagFollowers")
                followers = utils.columnsToDict(followers).keys()


                yield feed.deleteFeed(userId, itemId, convId, convType,
                                         convACL, convOwnerId, responseType,
                                         followers, tagId, deleteAll=deleteAll)


        #remove from itemLikes
        itemResponses = yield db.get_slice(convId, "itemResponses")
        itemResponses = utils.columnsToDict(itemResponses)
        itemLikes = yield db.get_slice(itemId, "itemLikes")
        itemLikes = utils.columnsToDict(itemLikes)
        responseType = "L"
        for userId in itemLikes:
            tuuid = itemLikes[userId]
            yield feed.deleteUserFeed(userId, itemType, tuuid)
            yield feed.deleteFeed(userId, itemId, convId, convType, convACL,
                                     convOwnerId, responseType, deleteAll=deleteAll)

        # if conv is being deleted, delete feed corresponding to commentLikes also.
        if itemId == convId:
            for tuuid in itemResponses:
                userId, responseId = itemResponses[tuuid].split(":")
                itemLikes = yield db.get_slice(responseId, "itemLikes")
                itemLikes = utils.columnsToDict(itemLikes)
                for userId in itemLikes:
                    tuuid = itemLikes[userId]
                    yield feed.deleteUserFeed(userId, itemType, tuuid)
                    yield feed.deleteFeed(userId, responseId, convId,
                                             convType, convACL, convOwnerId,
                                             responseType, deleteAll=deleteAll)

        #remove from itemResponses
        responseType = "C"
        for tuuid in itemResponses:
            userId, responseId = itemResponses[tuuid].split(":")
            if itemId == convId or (responseId == itemId):
                deleteFromFeed = (itemId == convId)
                yield feed.deleteUserFeed(userId, itemType, tuuid)
                yield feed.deleteFeed(userId, responseId, convId, convType,
                                         convACL, convOwnerId, responseType,
                                         deleteAll=deleteAll)
                if deleteAll:
                    yield db.insert(convId, "deletedConvs", '', responseId)
                    yield db.remove(convId, "itemResponses", tuuid)

        #update itemResponse Count
        if itemId != convId and deleteAll:
            responseCount = yield db.get_count(convId, "itemResponses")
            yield db.insert(convId, "items", str(responseCount), "responseCount", "meta")

        if itemId == convId:
            responseType="I"
            yield feed.deleteUserFeed(convOwnerId, convType, conv["meta"]["uuid"])
            yield feed.deleteFeed(convOwnerId, convId, convId, convType,
                                     convACL, convOwnerId, responseType,
                                     deleteAll=deleteAll)
        if deleteAll:
            fts.solr.deleteIndex(itemId)

        #TODO: update UI


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d =  self.renderItem(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == "responses":
                d = self._responses(request)
            if action == "likes":
                d = self._likes(request)

        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1:
            action = request.postpath[0]
            availableActions = ["new", "comment", "tag", "untag", "like",
                                "unlike", "remove"]
            if action in availableActions:
                d = getattr(self, "_" + request.postpath[0])(request)
            elif action == 'delete':
                d = self._remove(request, True)

        return self._epilogue(request, d)
