import uuid
import time
from telephus.cassandra     import ttypes
from twisted.internet       import defer
from social                 import db, base, utils, feed, plugins, tags, files
from social                 import constants, search, errors, notifications, _
from social.core            import Feed

# Expects all the basic arguments as well as some information
# about the comments and  to be available in kwargs.


@defer.inlineCallbacks
def _notify(notifyType, convId, timeUUID, **kwargs):
    deferreds = []
    convOwnerId = kwargs["convOwnerId"]
    convType = kwargs["convType"]
    myId = kwargs["myId"]
    toFetchEntities = []
    notifyId = ":".join([convId, convType, convOwnerId, notifyType])

    # List of people who will get the notification about current action
    if notifyType == "C":
        followers = yield db.get_slice(convId, "items",
                                       super_column="followers")
        toFetchEntities = recipients = [x.column.name for x in followers]
    elif notifyType == "LC":
        recipients = [kwargs["itemOwnerId"]]
        toFetchEntities = recipients + [convOwnerId]
    elif notifyType == "RFC":
        recipients = [kwargs["reportedBy"]] if myId == convOwnerId else [convOwnerId]
    elif notifyType == "FC" or notifyType == "UFC":
        recipients = [convOwnerId]
    else:
        toFetchEntities = recipients = [convOwnerId]

    # The actor must not be sent a notification
    recipients = [userId for userId in recipients if userId != myId]

    # Get all data that is required to send offline notifications
    entities = base.EntitySet(toFetchEntities)
    notify_d = entities.fetchData() if recipients else defer.succeed([])

    def _gotEntities(cols):
        if 'entities' in kwargs:
            kwargs['entities'].update(entities)
        else:
            kwargs['entities'] = entities

    def _sendNotifications(ignored):
        return notifications.notify(recipients, notifyId,
                                    myId, timeUUID, **kwargs)
    notify_d.addCallback(_gotEntities)
    notify_d.addCallback(_sendNotifications)

    deferreds.append(notify_d)
    yield defer.DeferredList(deferreds)


@defer.inlineCallbacks
def like(itemId, item, myId, orgId, me=None):
    try:
        cols = yield db.get(itemId, "itemLikes", myId)
        defer.returnValue(None)     # Ignore the request if we already liked it.
    except ttypes.NotFoundException:
        pass

    if not me:
        me = base.Entity(myId)
        yield me.fetchData()
    itemOwnerId = item["meta"]["owner"]
    extraEntities = [itemOwnerId]
    convId = item["meta"].get("parent", itemId)

    if convId != itemId:
        #get parent's meta data
        conv = yield db.get(convId, "items", super_column="meta")
        conv = utils.supercolumnsToDict([conv])
        commentText = item["meta"]["comment"]
        richText = item["meta"].get("richText", "False") == "True"
        commentSnippet = utils.toSnippet(commentText, 35, richText)
    else:
        conv = item
        commentSnippet = ""

    convOwnerId = conv["meta"]["owner"]
    convType = conv["meta"]["type"]
    convACL = conv["meta"]["acl"]

    # Update the likes count
    likesCount = int(item["meta"].get("likesCount", "0"))
    if likesCount % 5 == 3:
        likesCount = yield db.get_count(itemId, "itemLikes")
    item["meta"]["likesCount"] = str(likesCount + 1)

    yield db.insert(itemId, "items", item['meta']['likesCount'], "likesCount", "meta")

    timeUUID = uuid.uuid1().bytes

    # 1. add user to Likes list
    yield db.insert(itemId, "itemLikes", timeUUID, me.id)

    # Ignore adding to other's feeds if I am owner of the item
    if me.id != item["meta"]["owner"]:
        responseType = "L"

        # 2. add user to the followers list of parent item
        yield db.insert(convId, "items", "", me.id, "followers")

        # 3. update user's feed, feedItems, feed_*
        userItemValue = ":".join([responseType, itemId, convId, convType,
                                  convOwnerId, commentSnippet])
        yield db.insert(me.id, "userItems", userItemValue, timeUUID)
        if convType in plugins and plugins[convType].hasIndex:
            yield db.insert(me.id, "userItems_" + convType, userItemValue, timeUUID)

        # 4. update feeds
        feedItemVal = "%s:%s:%s:%s" % (responseType, myId, itemId,
                                       ','.join(extraEntities))
        yield Feed.push(myId, orgId, convId, conv, timeUUID, feedItemVal)
        if itemId != convId:
            if me.id != itemOwnerId:
                yield _notify("LC", convId, timeUUID, convType=convType,
                              convOwnerId=convOwnerId, myId=me.id,
                              itemOwnerId=itemOwnerId, me=me)
        else:
            if me.id != convOwnerId:
                yield _notify("L", convId, timeUUID, convType=convType,
                              convOwnerId=convOwnerId, myId=me.id, me=me)
    defer.returnValue(item)


@defer.inlineCallbacks
def unlike(itemId, item, myId, orgId):
    # Make sure that I liked this item
    try:
        cols = yield db.get(itemId, "itemLikes", myId)
        likeTimeUUID = cols.column.value
    except ttypes.NotFoundException:
        defer.returnValue(None)

    convId = item["meta"].get("parent", itemId)
    if convId != itemId:
        conv = yield db.get(convId, "items", super_column="meta")
        conv = utils.supercolumnsToDict([conv])
    else:
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
    item['meta']['likesCount'] = likesCount - 1
    yield db.insert(itemId, "items", str(likesCount - 1), "likesCount", "meta")

    responseType = 'L'
    # 2. Don't remove the user from followers list
    #    (use can also become follower by responding to item,
    #        so user can't be removed from followers list)

    # Ignore if i am owner of the item
    if myId != item["meta"]["owner"]:
        # 3. delete from user's feed, feedItems, feed_*
        likeUpdateVal = "L:%s:%s:%s" % (myId, itemId, item['meta']['owner'])
        yield Feed.unpush(myId, orgId, convId, conv, likeUpdateVal)

        # FIX: if user updates more than one item at exactly same time,
        #      one of the updates will overwrite the other. Fix it.
        yield db.remove(myId, "userItems", likeTimeUUID)
        if convType in plugins and plugins[convType].hasIndex:
            yield db.remove(myId, "userItems_" + convType, likeTimeUUID)
    defer.returnValue(item)


@defer.inlineCallbacks
def _comment(convId, conv, comment, snippet, myId, orgId, richText, reviewed):
    convType = conv["meta"].get("type", "status")

    # 1. Create the new item
    timeUUID = uuid.uuid1().bytes
    meta = {"owner": myId, "parent": convId, "comment": comment,
            "timestamp": str(int(time.time())), "org": orgId,
            "uuid": timeUUID, "richText": str(richText)}
    followers = {myId: ''}
    itemId = utils.getUniqueKey()
    if snippet:
        meta['snippet'] = snippet

    # 1.5. Check if the comment matches any of the keywords
    entities = base.EntitySet([myId, orgId])
    yield entities.fetchData(['basic', 'admins'])
    orgAdmins = entities[orgId].admins.keys()
    if orgAdmins:
        matchedKeywords = yield utils.watchForKeywords(orgId, comment)
        if matchedKeywords:
            if reviewed:
                # Add item to list of items that matched this keyword
                # and notify the administrators about it.
                for keyword in matchedKeywords:
                    yield db.insert(orgId + ":" + keyword, "keywordItems",
                                    itemId + ":" + convId, timeUUID)
                    yield notifications.notify(orgAdmins, ':KW:' + keyword,
                                               myId, entities=entities)

            else:
                # This item contains a few keywords that are being monitored
                # by the admin and cannot be posted unless reviewOK is set.
                defer.returnValue((None, convId, {convId: conv}, matchedKeywords))

    # 1.9. Actually store the item
    yield db.batch_insert(itemId, "items", {'meta': meta})

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
    if convType in plugins and plugins[convType].hasIndex:
        yield db.insert(myId, "userItems_" + convType, userItemValue, timeUUID)

    # 5. Update my feed.
    feedItemVal = "%s:%s:%s" % (responseType, myId, itemId)
    yield Feed.push(myId, orgId, convId, conv, timeUUID, feedItemVal)

    yield _notify("C", convId, timeUUID, convType=convType,
                  convOwnerId=convOwnerId, myId=myId, me=entities[myId],
                  comment=comment, richText=richText)
    search.solr.updateItemIndex(itemId, {'meta': meta}, orgId, conv=conv)
    items = {itemId: {'meta': meta}, convId: conv}
    defer.returnValue((itemId, convId, items, None))


@defer.inlineCallbacks
def tag(itemId, item, tagName, myId, orgId):
    if "parent" in item["meta"]:
        raise errors.InvalidRequest(_("Tag cannot be applied on a comment"))

    (tagId, tag) = yield tags._ensureTag(tagName, myId, orgId)
    if tagId in item.get("tags", {}):
        raise errors.InvalidRequest(_("Tag already exists on the choosen item"))

    d1 = db.insert(itemId, "items", myId, tagId, "tags")
    d2 = db.insert(tagId, "tagItems", itemId, item["meta"]["uuid"])
    d3 = db.get_slice(tagId, "tagFollowers")

    tagItemsCount = int(tag.get("itemsCount", "0")) + 1
    if tagItemsCount % 10 == 7:
        tagItemsCount = yield db.get_count(tagId, "tagItems")
        tagItemsCount += 1
    db.insert(orgId, "orgTags", "%s" % tagItemsCount, "itemsCount", tagId)

    result = yield defer.DeferredList([d1, d2, d3])
    followers = utils.columnsToDict(result[2][1]).keys()

    if followers:
        timeUUID = uuid.uuid1().bytes
        feedUpdateVal = "T:%s:%s::%s" % (myId, itemId, tagId)
        yield Feed.push(myId, orgId, itemId, item, timeUUID,
                        feedUpdateVal, feeds=followers)

    defer.returnValue((tagId, tag))

    #TODO: Send notification to the owner of conv


@defer.inlineCallbacks
def untag(itemId, item, tagId, tag, myId, orgId):
    if "parent" in item:
        raise errors.InvalidRequest(_("Tags cannot be applied or removed from comments"))

    if tagId not in item.get("tags", {}):
        raise errors.InvalidRequest(_("No such tag on the item"))  # No such tag on item

    d1 = db.remove(itemId, "items", tagId, "tags")
    d2 = db.remove(tagId, "tagItems", item["meta"]["uuid"])
    d3 = db.get_slice(tagId, "tagFollowers")

    try:
        itemsCountCol = yield db.get(orgId, "orgTags", "itemsCount", tagId)
        tagItemsCount = int(itemsCountCol.column.value) - 1
        if tagItemsCount % 10 == 7:
            tagItemsCount = yield db.get_count(tagId, "tagItems")
            tagItemsCount = tagItemsCount - 1
        db.insert(orgId, "orgTags", "%s" % tagItemsCount, "itemsCount", tagId)
    except ttypes.NotFoundException:
        pass
    result = yield defer.DeferredList([d1, d2, d3])
    followers = utils.columnsToDict(result[2][1]).keys()


    feedUpdateVal = "T:%s:%s::%s" % (myId, itemId, tagId)
    yield Feed.unpush(myId, orgId, itemId, item,
                      feedUpdateVal, followers + [myId])


@defer.inlineCallbacks
def removeFromFeed(itemId, item, myId, orgId):
    convId = item["meta"].get("parent", itemId)
    itemOwnerId = item["meta"]["owner"]
    if itemId != convId:
        conv = yield db.get_slice(convId, "items", ["meta", "tags"])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.InvalidRequest(_('Conversation does not exist!'))

        convOwnerId = conv["meta"]["owner"]
    else:
        conv = item
        convOwnerId = itemOwnerId
    deferreds = []
    convType = conv["meta"].get('type', 'status')
    convACL = conv["meta"]["acl"]
    timestamp = str(int(time.time()))
    itemUUID = item["meta"]["uuid"]

    # Just remove from my feed and block any further updates of that
    # item from coming to my feed.
    feedId = myId
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


@defer.inlineCallbacks
def delete(itemId, item, myId, orgId):
    convId = item["meta"].get("parent", itemId)
    itemOwnerId = item["meta"]["owner"]

    if itemId == convId:
        conv = item
        convOwnerId = itemOwnerId
    else:
        conv = yield db.get_slice(convId, "items", ["meta", "tags"])
        conv = utils.supercolumnsToDict(conv)
        if not conv:
            raise errors.InvalidRequest(_('Conversation does not exist!'))

        convOwnerId = conv["meta"]["owner"]

    # TODO: Admin actions.
    # Do I have permission to delete the comment
    if (itemOwnerId != myId and convOwnerId != myId):
        raise errors.PermissionDenied(_("You must either own the comment or the conversation to delete this comment"))

    deferreds = []
    convType = conv["meta"].get('type', 'status')
    convACL = conv["meta"]["acl"]
    timestamp = str(int(time.time()))
    itemUUID = item["meta"]["uuid"]

    # The conversation is lazy deleted.
    # If it is the comment being deleted, rollback all feed updates
    # that were made due to this comment and likes on this comment.
    d = deleteItem(itemId, myId, orgId, item, conv)
    deferreds.append(d)

    yield defer.DeferredList(deferreds)
    defer.returnValue(conv)


@defer.inlineCallbacks
def new(request, authInfo, convType, richText=False):
    if convType not in plugins:
        raise errors.BaseError('Unsupported item type', 400)
    myId = authInfo.username
    orgId = authInfo.organization
    entities = base.EntitySet([myId, orgId])
    yield entities.fetchData(['basic', 'admins'])

    plugin = plugins[convType]
    convId = utils.getUniqueKey()
    conv = yield plugin.create(request, entities[myId], convId, richText)
    orgAdminIds = entities[orgId].admins.keys()
    if orgAdminIds:
        text = ''
        monitoredFields = getattr(plugin, 'monitoredFields', {})
        for superColumnName in monitoredFields:
            for columnName in monitoredFields[superColumnName]:
                if columnName in conv[superColumnName]:
                    text = " ".join([text, conv[superColumnName][columnName]])
        matchedKeywords = yield utils.watchForKeywords(orgId, text)

        if matchedKeywords:
            reviewOK = utils.getRequestArg(request, "_review") == "1"
            if reviewOK:
                # Add conv to list of items that matched this keyword
                # and notify the administrators about it.
                orgAdmins = base.EntitySet(orgAdminIds)
                yield orgAdmins.fetchData()
                entities.update(orgAdmins)
                for keyword in matchedKeywords:
                    yield db.insert(orgId + ":" + keyword, "keywordItems",
                                    convId, conv['meta']['uuid'])
                    yield notifications.notify(orgAdminIds, ':KW:' + keyword,
                                               myId, entities=entities)
            else:
                # This item contains a few keywords that are being monitored
                # by the admin and cannot be posted unless reviewOK is set.
                defer.returnValue((None, None, matchedKeywords))

    #
    # Save the new item to database and index it.
    #
    yield db.batch_insert(convId, "items", conv)
    yield files.pushfileinfo(myId, orgId, convId, conv)
    search.solr.updateItemIndex(convId, conv, orgId)

    #
    # Push item to feeds and userItems
    #
    timeUUID = conv["meta"]["uuid"]
    convACL = conv["meta"]["acl"]
    deferreds = []
    responseType = 'I'

    # Push to feeds
    feedUpdateVal = "I:%s:%s" % (myId, convId)
    d = Feed.push(myId, orgId, convId, conv, timeUUID,
                  feedUpdateVal, promoteActor=True)
    deferreds.append(d)

    # Save in user items.
    userItemValue = ":".join([responseType, convId, convId, convType, myId, ''])
    d = db.insert(myId, "userItems", userItemValue, timeUUID)
    deferreds.append(d)
    if plugins[convType].hasIndex:
        d = db.insert(myId, "userItems_%s" % (convType), userItemValue, timeUUID)
        deferreds.append(d)

    yield defer.DeferredList(deferreds)
    defer.returnValue((convId, conv, None))


@defer.inlineCallbacks
def likes(itemId, item):
    itemLikes = yield db.get_slice(itemId, "itemLikes")

    users = [col.column.name for col in itemLikes]
    if len(users) <= 0:
        defer.returnValue(({}, []))

    entities = base.EntitySet(users + [item['meta']['owner']])
    yield entities.fetchData()
    defer.returnValue((entities, users))


def _cleanupMissingComments(convId, missingIds, itemResponses):
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


@defer.inlineCallbacks
def responses(myId, itemId, item, start=''):
    toFetchEntities = set()
    itemResponses = yield db.get_slice(itemId, "itemResponses",
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
    entities = base.EntitySet(toFetchEntities)

    d3 = db.multiget_slice(responseKeys + [itemId], "itemLikes", [myId])
    d2 = db.multiget_slice(responseKeys + [itemId], "items", ["meta"])
    d1 = entities.fetchData()

    fetchedItems = yield d2
    myLikes = yield d3
    yield d1

    fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
    fetchedLikes = utils.multiColumnsToDict(myLikes)

    # Do some error correction/consistency checking to ensure that the
    # response items actually exist. I don't know of any reason why these
    # items may not exist.
    missingIds = [x for x, y in fetchedItems.items() if not y]
    if missingIds:
        yield _cleanupMissingComments(itemId, missingIds, itemResponses)

    ret = {'items': fetchedItems, 'entities': entities,
            'myLikes': myLikes, 'responses': {itemId: responseKeys}}
    if nextPageStart:
        ret['oldest'] = utils.encodeKey(nextPageStart)
    defer.returnValue(ret)


@defer.inlineCallbacks
def deleteItem(itemId, userId, orgId, item=None, conv=None,):
    if not item:
        item = yield db.get_slice(itemId, "items", ["meta", "tags"])
        item = utils.supercolumnsToDict(item)

    meta = item["meta"]
    convId = meta.get("parent", itemId)
    itemUUID = meta["uuid"]
    itemOwnerId = meta["owner"]
    timestamp = str(int(time.time()))

    d = db.insert(itemId, "items", "deleted", "state", "meta")
    deferreds = [d]
    if not conv:
        conv = yield db.get_slice(convId, "items", ['meta', 'tags'])
        conv = utils.supercolumnsToDict(conv)

    plugin = plugins[conv['meta']['type']]
    if convId == itemId:
        # Delete from tagItems.
        for tagId in item.get("tags", {}):
            d = db.remove(tagId, "tagItems", itemUUID)
            deferreds.append(d)

        # Actually, delete the conversation.
        d1 = db.insert(itemOwnerId, 'deletedConvs', timestamp, itemId)
        d1.addCallback(lambda x: search.solr.delete(itemId))
        d1.addCallback(lambda x: files.deleteFileInfo(userId, orgId, itemId, item))
        d2 = plugin.delete(userId, convId, conv)
        deferreds.extend([d1, d2])

    else:
        convType = conv["meta"]["type"]
        convOwnerId = conv["meta"]["owner"]
        convACL = conv["meta"]["acl"]

        d1 = db.insert(convId, 'deletedConvs', timestamp, itemId)
        d2 = db.remove(convId, 'itemResponses', itemUUID)
        d2.addCallback(lambda x: db.get_count(convId, "itemResponses"))
        d2.addCallback(lambda x: db.insert(convId, 'items', \
                                 str(x), 'responseCount', 'meta'))
        d2.addCallback(lambda x: search.solr.delete(itemId))
        deferreds.extend([d1, d2])

        # Rollback changes to feeds caused by this comment
        d = db.get_slice(itemId, "itemLikes")

        def removeLikeFromFeeds(result):
            likes = utils.columnsToDict(result)
            removeLikeDeferreds = []
            for actorId, likeUUID in likes.items():
                likeUpdateVal = "L:%s:%s:%s" % (actorId, itemId, itemOwnerId)
                d1 = feed.deleteUserFeed(actorId, convType, likeUUID)
                d2 = Feed.unpush(actorId, orgId, convId, conv, likeUpdateVal)
                removeLikeDeferreds.extend([d1, d2])
            return defer.DeferredList(removeLikeDeferreds)
        d.addCallback(removeLikeFromFeeds)
        deferreds.append(d)

        # Delete comment from comment owner's userItems
        d = feed.deleteUserFeed(itemOwnerId, convType, itemUUID)
        deferreds.append(d)

        # Rollback updates done to comment owner's follower's feeds.
        responseUpdateVal = "Q:%s:%s" if convType == "question" else "C:%s:%s"
        responseUpdateVal = responseUpdateVal % (itemOwnerId, itemId)
        d = Feed.unpush(itemOwnerId, orgId, convId, conv, responseUpdateVal)
        deferreds.append(d)

    yield defer.DeferredList(deferreds)
