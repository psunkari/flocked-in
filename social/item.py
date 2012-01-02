import uuid
import time
import re

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server

from social             import base, db, utils, feed, config
from social             import plugins, constants, tags, search
from social             import notifications, _, errors, files
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log


#
# Create a new conversation item.
#
@defer.inlineCallbacks
def _createNewItem(request, myId, myOrgId, richText=False):
    convType = utils.getRequestArg(request, "type")
    if convType not in plugins:
        raise errors.BaseError('Unsupported item type', 400)

    plugin = plugins[convType]
    convId, conv = yield plugin.create(request, myId, myOrgId, richText)
    yield files.pushfileinfo(myId, myOrgId, convId, conv)

    timeUUID = conv["meta"]["uuid"]
    convACL = conv["meta"]["acl"]

    deferreds = []
    responseType = 'I'

    # Push to all the feeds.
    d = feed.pushToFeed(myId, timeUUID, convId, None,
                        responseType, convType, myId, myId)
    deferreds.append(d)

    d = feed.pushToOthersFeed(myId, myOrgId, timeUUID, convId, None, convACL,
                              responseType, convType, myId)
    deferreds.append(d)

    # Save in user items.
    userItemValue = ":".join([responseType, convId, convId, convType, myId, ''])
    d = db.insert(myId, "userItems", userItemValue, timeUUID)
    deferreds.append(d)

    if plugins[convType].hasIndex:
        d = db.insert(myId, "userItems_%s"%(convType), userItemValue, timeUUID)
        deferreds.append(d)

    yield defer.DeferredList(deferreds)
    defer.returnValue((convId, conv))


@defer.inlineCallbacks
def _comment(request, myId, orgId, convId=None, richText=False):
    snippet, comment = utils.getTextWithSnippet(request, "comment",
                                        constants.COMMENT_PREVIEW_LENGTH, richText=richText)
    if not comment:
        raise errors.MissingParams([_("Comment")])

    # 0. Fetch conversation and see if I have access to it.
    (convId, conv) = yield utils.getValidItemId(request, "parent", myOrgId=orgId, myId=myId, itemId=convId)
    convType = conv["meta"].get("type", "status")
    me = yield db.get_slice(myId, "entities", ['basic'])
    me = utils.supercolumnsToDict(me)

    # 1. Create and add new item
    timeUUID = uuid.uuid1().bytes
    meta = {"owner": myId, "parent": convId, "comment": comment,
            "timestamp": str(int(time.time())),
            "uuid": timeUUID, "richText": str(richText)}
    followers = {myId: ''}
    itemId = utils.getUniqueKey()
    if snippet:
        meta['snippet'] = snippet

    yield db.batch_insert(itemId, "items", {'meta': meta,
                                            'followers': followers})

    # 2. Update response count and add myself to the followers of conv
    convOwnerId = conv["meta"]["owner"]
    convType = conv["meta"]["type"]
    responseCount = int(conv["meta"].get("responseCount", "0"))
    if responseCount % 5 == 3:
        responseCount = yield db.get_count(convId, "itemResponses")

    responseCount += 1
    conv['meta']['responseCount'] = responseCount
    convUpdates = {"responseCount": str(responseCount)}
    yield db.batch_insert(convId, "items", {"meta": convUpdates,
                                            "followers": followers})

    # 3. Add item as response to parent
    yield db.insert(convId, "itemResponses",
                    "%s:%s" % (myId, itemId), timeUUID)

    # 4. Update userItems and userItems_*
    responseType = "Q" if convType == "question" else 'C'
    commentSnippet = utils.toSnippet(comment, 35, richText)
    userItemValue = ":".join([responseType, itemId, convId, convType,
                              convOwnerId, commentSnippet])
    yield db.insert(myId, "userItems", userItemValue, timeUUID)
    if plugins.has_key(convType) and plugins[convType].hasIndex:
        yield db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

    # 5. Update my feed.
    yield feed.pushToFeed(myId, timeUUID, itemId, convId, responseType,
                          convType, convOwnerId, myId, promote=False)

    # 6. Push to other's feeds
    convACL = conv["meta"].get("acl", "company")
    yield feed.pushToOthersFeed(myId, orgId, timeUUID, itemId, convId, convACL,
                                responseType, convType, convOwnerId,
                                promoteActor=False)

    yield _notify("C", convId, timeUUID, convType=convType,
                      convOwnerId=convOwnerId, myId=myId, me=me,
                      comment=comment, richText=richText)
    search.solr.updateItem(itemId, {'meta':meta}, orgId, conv=conv)
    items = {itemId: {'meta':meta}, convId: conv}
    defer.returnValue((itemId, convId, items))


# Expects all the basic arguments as well as some information
# about the comments and likes to be available in kwargs.
@defer.inlineCallbacks
def _notify(notifyType, convId, timeUUID, **kwargs):
    deferreds = []
    convOwnerId = kwargs["convOwnerId"]
    convType = kwargs["convType"]
    myId = kwargs["myId"]
    notifyId = ":".join([convId, convType, convOwnerId, notifyType])

    # List of people who will get the notification about current action
    if notifyType == "C":
        followers = yield db.get_slice(convId, "items", super_column="followers")
        toFetchEntities = recipients = [x.column.name for x in followers]
    elif notifyType == "LC":
        recipients = [kwargs["itemOwnerId"]]
        toFetchEntities = recipients + [convOwnerId]
    else:
        toFetchEntities = recipients = [convOwnerId]

    # The actor must not be sent a notification
    recipients = [userId for userId in recipients if userId != myId]

    # Get all data that is required to send offline notifications
    # XXX: Entities generally contains a map of userId => {Basic: Data}
    #      In this case it will contain userId => data directly.
    notify_d = db.multiget_slice(toFetchEntities, "entities",
                        ["name", "emailId", "notify"], super_column="basic") \
                        if recipients else defer.succeed([])
    def _gotEntities(cols):
        entities = utils.multiColumnsToDict(cols)
        kwargs.setdefault('entities', {}).update(entities)
    def _sendNotifications(ignored):
        return notifications.notify(recipients, notifyId,
                                    myId, timeUUID, **kwargs)
    notify_d.addCallback(_gotEntities)
    notify_d.addCallback(_sendNotifications)

    deferreds.append(notify_d)
    yield defer.DeferredList(deferreds)


class ItemResource(base.BaseResource):
    isLeaf = True

    def _cleanupMissingComments(self, convId, missingIds, itemResponses):
        missingKeys = []
        for response in itemResponses:
            userKey, responseKey = response.column.value.split(':')
            if responseKey in missingIds:
                missingKeys.append(response.column.name)

        d1 = db.batch_remove({'itemResponses': [convId]}, names=missingKeys)
        d1.addCallback(lambda x: db.get_count(convId, "itemResponses"))
        d1.addCallback(lambda x: db.insert(convId, 'items',\
                                 str(x), 'responseCount', 'meta'))
        return d1


    @profile
    @defer.inlineCallbacks
    @dump_args
    def renderItem(self, request, toFeed=False):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

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

        relation = Relation(myKey, [])
        yield defer.DeferredList([relation.initGroupsList(),
                                  relation.initSubscriptionsList()])
        args["relations"] = relation

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
            toFetchEntities.update(conv['meta']['target'].split(','))

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

        subscriptions = list(relation.subscriptions)
        likes = yield db.get_slice(convId, "itemLikes", subscriptions) \
                            if subscriptions else defer.succeed([])
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

        fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
        fetchedEntities = utils.multiSuperColumnsToDict(fetchedEntities)
        myLikes = utils.multiColumnsToDict(myLikes)
        fetchedTags = utils.supercolumnsToDict(fetchedTags)

        # Do some error correction/consistency checking to ensure that the
        # response items actually exist. I don't know of any reason why these
        # items may not exist.
        missingIds = [x for x,y in fetchedItems.items() if not y]
        if missingIds:
            yield self._cleanupMissingComments(convId, missingIds, itemResponses)

        args["items"].update(fetchedItems)
        args["entities"].update(fetchedEntities)
        args["myLikes"] = myLikes
        args["tags"] = fetchedTags
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
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        convId, conv = yield _createNewItem(request, myId, args['orgId'])
        entities = {myId: args['me']}
        target = conv['meta'].get('target', None)
        if target:
            toFetchEntities = set(target.split(','))
            cols = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
            entities.update(utils.multiSuperColumnsToDict(cols))

        relation = Relation(myId, [])
        yield relation.initGroupsList()

        data = {"items":{convId:conv}, "relations": relation,
                "entities":entities, "script": True}
        args.update(data)
        onload = "(function(obj){$$.convs.load(obj);$('#sharebar-attach-uploaded').empty();})(this);"
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
        orgId = args['orgId']

        # Get the item and the conversation
        (itemId, item) = yield utils.getValidItemId(request, "id")
        extraEntities = [item["meta"]["owner"]]

        # Check if I already liked the item
        try:
            cols = yield db.get(itemId, "itemLikes", myId)
            defer.returnValue(None)     # Ignore the request if we already liked it.
        except ttypes.NotFoundException:
            pass

        richText = item['meta'].get('richText', 'False')== 'True'
        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
            commentText = item["meta"].get("comment")
            if commentText:
                commentSnippet = utils.toSnippet(commentText, 35, richText)
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

        item["meta"]["likesCount"] = str(likesCount + 1)
        args["items"] = {itemId: item}
        args["myLikes"] = {itemId:[myId]}
        timeUUID = uuid.uuid1().bytes

        # 1. add user to Likes list
        yield db.insert(itemId, "itemLikes", timeUUID, myId)

        # Ignore adding to other's feeds if I am owner of the item
        if myId != item["meta"]["owner"]:
            responseType = "L"

            # 2. add user to the followers list of parent item
            yield db.insert(convId, "items", "", myId, "followers")

            # 3. update user's feed, feedItems, feed_*
            userItemValue = ":".join([responseType, itemId, convId, convType,
                                      convOwnerId, commentSnippet])
            yield db.insert(myId, "userItems", userItemValue, timeUUID)
            if plugins.has_key(convType) and plugins[convType].hasIndex:
                yield db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

            yield feed.pushToFeed(myId, timeUUID, itemId, convId, responseType,
                                  convType, convOwnerId, myId,
                                  entities=extraEntities, promote=False)

            # 4. update feed, feedItems, feed_* of user's followers
            yield feed.pushToOthersFeed(myId, orgId, timeUUID, itemId, convId, convACL,
                                        responseType, convType, convOwnerId,
                                        entities=extraEntities, promoteActor=False)

        if itemId != convId:
            itemOwnerId = item["meta"]["owner"]
            if myId != itemOwnerId:
                yield _notify("LC", convId, timeUUID, convType=convType,
                                  convOwnerId=convOwnerId, myId=myId,
                                  itemOwnerId=itemOwnerId, me=args["me"])
            yield renderScriptBlock(request, "item.mako", "item_footer", False,
                                    "#item-footer-%s"%(itemId), "set",
                                    args=[itemId], **args)
        else:
            if myId != convOwnerId:
                yield _notify("L", convId, timeUUID, convType=convType,
                                  convOwnerId=convOwnerId, myId=myId, me=args["me"])

            relation = Relation(myId, [])
            yield relation.initSubscriptionsList()
            subscriptions = list(relation.subscriptions)
            if subscriptions:
                likes = yield db.get_slice(convId, "itemLikes", subscriptions)
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
        orgId = args['orgId']

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
        yield db.insert(itemId, "items", str(likesCount-1), "likesCount", "meta")

        responseType = 'L'
        # 2. Don't remove the user from followers list
        #    (use can also become follower by responding to item,
        #        so user can't be removed from followers list)

        # Ignore if i am owner of the item
        if myId == item["meta"]["owner"]:
            # 3. delete from user's feed, feedItems, feed_*
            yield feed.deleteFromFeed(myId, itemId, convId,
                                      convType, myId, responseType)

            # 4. delete from feed, feedItems, feed_* of user's followers
            yield feed.deleteFromOthersFeed(myId, orgId, itemId, convId, convType,
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

            entities = {}
            if toFetchEntities:
                entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
                entities = utils.multiSuperColumnsToDict(entities)

            args["entities"] = entities

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
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        itemId, convId, items = yield _comment(request, myId, orgId)

        # Finally, update the UI
        entities = yield db.get(myId, "entities", super_column="basic")
        entities = {myId: utils.supercolumnsToDict([entities])}
        args = {"entities": entities, "items": items, "me": entities[myId]}

        numShowing = utils.getRequestArg(request, "nc") or "0"
        numShowing = int(numShowing) + 1
        responseCount = items[convId]['meta']['responseCount']
        isItemView = (utils.getRequestArg(request, "_pg") == "/item")
        yield renderScriptBlock(request, 'item.mako', 'conv_comments_head',
                        False, '#comments-header-%s' % (convId), 'set',
                        args=[convId, responseCount, numShowing, isItemView], **args)

        yield renderScriptBlock(request, 'item.mako', 'conv_comment', False,
                                '#comments-%s' % convId, 'append', True,
                                handlers={"onload": "(function(){$('.comment-input', '#comment-form-%s').val(''); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();" % (convId, convId, numShowing)},
                                args=[convId, itemId], **args)


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

        fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
        fetchedEntities = utils.multiSuperColumnsToDict(fetchedEntities)
        fetchedLikes = utils.multiColumnsToDict(myLikes)

        # Do some error correction/consistency checking to ensure that the
        # response items actually exist. I don't know of any reason why these
        # items may not exist.
        missingIds = [x for x,y in fetchedItems.items() if not y]
        if missingIds:
            yield self._cleanupMissingComments(convId, missingIds, itemResponses)

        args.update({"convId": convId, "isFeed": isFeed, "items":{}, "entities": {}})
        args["items"].update(fetchedItems)
        args["entities"].update(fetchedEntities)
        args["myLikes"] = myLikes
        args["responses"] = {convId: responseKeys}
        if nextPageStart:
            args["oldest"] = utils.encodeKey(nextPageStart)

        if isFeed:
            args["isItemView"] = False
            showing = len(responseKeys)
            handler = {"onload":"(function(){$$.convs.showHideComponent('%s', 'comments', true); $('[name=\"nc\"]', '#comment-form-%s').val('%s');})();"%(convId, convId, showing)}
            yield renderScriptBlock(request, "item.mako", 'conv_comments',
                        not self._ajax, '#conv-comments-wrapper-%s' % convId,
                        'set', True, handlers=handler, **args)
        else:
            landing = not self._ajax
            showing = utils.getRequestArg(request, "nc") or "0"
            showing = int(showing) + len(responseKeys)
            args["showing"] = showing
            args["total"] = int(args["items"][convId]["meta"].get("responseCount", "0"))
            args["isItemView"] = True

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

        decoded = tagName.decode('utf-8', 'replace')
        if len(decoded) > 50:
            raise errors.InvalidRequest(_('Tag cannot be more than 50 characters long'))
        if not re.match('^[\w-]*$', decoded):
            raise errors.InvalidRequest(_('Tag can only include numerals, alphabet and hyphens (-)'))

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
        if followers:
            yield feed.pushToOthersFeed(myId, orgId, timeUUID, itemId, itemId,
                                convACL, responseType, convType, convOwnerId,
                                others=followers, tagId=tagId, promoteActor=False)

        #TODO: Send notification to the owner of conv


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
                                  myId, responseType, tagId=tagId)

        if followers:
            yield feed.deleteFromOthersFeed(myId, orgId, itemId, convId, convType,
                                            convACL, convOwnerId, responseType,
                                            others=followers, tagId=tagId)
        request.write("$('#conv-tags-%s').children('[tag-id=\"%s\"]').remove();" % (convId, tagId));


    @defer.inlineCallbacks
    def _remove(self, request):
        (itemId, item) = yield utils.getValidItemId(request, 'id', columns=['tags'])
        convId = item["meta"].get("parent", itemId)
        itemOwnerId = item["meta"]["owner"]
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization

        comment = True
        if itemId == convId:
            conv = item
            comment = False
            convOwnerId = itemOwnerId
        else:
            conv = yield db.get_slice(convId, "items", ["meta"])
            conv = utils.supercolumnsToDict(conv)
            if not conv:
                raise errors.InvalidRequest(_('Conversation does not exist!'))

            convOwnerId = conv["meta"]["owner"]

        # For comments it's always delete.
        # For conversations it is delete if I own the conversation
        # If I don't own the conversation and the request
        #       is coming from my feed then hide it from my feed
        # TODO: Admin actions.

        delete = False
        if comment or convOwnerId == myId:
            delete = True

        # Do I have permission to delete the comment
        if comment and (itemOwnerId != myId and convOwnerId != myId):
            raise errors.PermissionDenied(_("You must either own the comment or the conversation to delete this comment"))

        # Do I have permission to remove item from the given feed.
        # Note that If I own the conversation, I don't have to check this
        elif not delete:
            feedId = utils.getRequestArg(request, 'feedId') or myId
            if feedId != myId:
                raise errors.PermissionDenied(_("You don't have permission to delete this item from the feed"))

        deferreds = []
        convType = conv["meta"].get('type', 'status')
        convACL = conv["meta"]["acl"]
        timestamp = str(int(time.time()))
        itemUUID = item["meta"]["uuid"]

        if delete:
            # The conversation is lazy deleted.
            # If it is the comment being deleted, rollback all feed updates
            # that were made due to this comment and likes on this comment.

            # Delete from tagItems and follower feeds.
            if not comment and "tags" in conv:
                for tagId in conv["tags"]:
                    d = db.remove(tagId, "tagItems", itemUUID)
                    deferreds.append(d)

            # We maintain an index of all deleted items by ownerId and by
            # convId - convId is used as key for comments and ownerId for
            # conversations. Also mark the item as deleted, update responses
            # and update deleted index
            d = db.insert(itemId, 'items', timestamp, 'deleted', 'meta')
            deferreds.append(d)
            if comment:
                d1 = db.insert(convId, 'deletedConvs', timestamp, itemId)
                d2 = db.remove(convId, 'itemResponses', itemUUID)
                d2.addCallback(lambda x: db.get_count(convId, "itemResponses"))
                d2.addCallback(lambda x: db.insert(convId, 'items',\
                                         str(x), 'responseCount', 'meta'))
                d2.addCallback(lambda x: search.solr.delete(itemId))
                deferreds.extend([d1, d2])
            else:
                d1 = db.insert(convOwnerId, 'deletedConvs', timestamp, convId)
                d1.addCallback(lambda x: search.solr.delete(itemId))
                d1.addCallback(lambda x: files.deleteFileInfo(myId, orgId, convId, conv))
                deferreds.append(d1)

            # Rollback changes to feeds.
            if comment:
                d = db.get_slice(itemId, "itemLikes")
                def removeLikeFromFeeds(result):
                    likes = utils.columnsToDict(result)
                    removeLikeDeferreds = []
                    for actorId, likeUUID in likes.items():
                        d1 = feed.deleteUserFeed(actorId, convType, likeUUID)
                        d2 = feed.deleteFeed(actorId, orgId, itemId, convId, convType,
                                    convACL, convOwnerId, 'L', deleteAll=True)
                        removeLikeDeferreds.extend([d1, d2])
                    return defer.DeferredList(removeLikeDeferreds)
                d.addCallback(removeLikeFromFeeds)
                deferreds.append(d)

                # Delete comment from comment owner's userItems
                d = feed.deleteUserFeed(itemOwnerId, convType, itemUUID)
                deferreds.append(d)

                # Rollback updates done to comment owner's follower's feeds.
                responseType = "Q" if convType == "question" else 'C'
                d = feed.deleteFeed(itemOwnerId, orgId, itemId, convId, convType,
                                    convACL, convOwnerId, responseType, deleteAll=True)
                deferreds.append(d)

        else:
            # Just remove from my feed and block any further updates of that
            # item from coming to my feed.
            d1 = db.get_slice(feedId, "feedItems", super_column=convId)
            @defer.inlineCallbacks
            def removeConvFromFeed(x):
                timestamps = [col.column.name for col in x]
                if timestamps:
                    yield db.batch_remove({'feed': [feedId]}, names=timestamps)
                else:
                    yield db.remove(feedId, 'feed', conv['meta']['uuid'])
                yield db.remove(feedId, 'feedItems', super_column=convId)

            d1.addCallback(removeConvFromFeed)
            d2 = db.insert(convId, 'items', timestamp, myId, 'unfollowed')

            deferreds.extend([d1, d2])

        # Wait till all the operations are finished!
        yield defer.DeferredList(deferreds)

        # Update the user interface
        request.write("$$.convs.remove('%s', '%s');"%(convId,itemId))


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
                d = self._remove(request)

        return self._epilogue(request, d)




#
# RESTful API for managing items.
#
class APIItemResource(base.APIBaseResource):

    @defer.inlineCallbacks
    def _newItem(self, request):
        token = self._ensureAccessScope(request, 'post-item')
        convId, conv = yield _createNewItem(request, token.user,
                                            token.org, richText=True)
        self._success(request, 201, {'id': convId})


    @defer.inlineCallbacks
    def _newComment(self, request):
        token = self._ensureAccessScope(request, 'post-item')
        convId = request.postpath[0]
        itemId, convId, items = yield _comment(request, token.user, token.org,
                                               convId=convId, richText=True)
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

