import uuid
import time
import re
import json
try:
    import cPickle as pickle
except:
    import pickle

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server

from social             import base, db, utils, feed, config
from social             import plugins, constants, tags, search
from social             import notifications, _, errors, files
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, getBlock, renderScriptBlock
from social.logging     import profile, dump_args, log

#
# Create a new conversation item.
# Returns a tuple:
#   1. (convId, conv, None) if no keywords match
#      or user is okay with admin review on this item
#   2. (None, None, keywords) if keywords match and the user must be asked
#      if it is okay to sent it to admin for review.
#
@defer.inlineCallbacks
def _createNewItem(request, myId, myOrgId, richText=False):
    convType = utils.getRequestArg(request, "type")
    if convType not in plugins:
        raise errors.BaseError('Unsupported item type', 400)

    plugin = plugins[convType]
    convId = utils.getUniqueKey()
    conv, attachments = yield plugin.create(request, myId, myOrgId, richText)

    #
    # Check if this item contains any keywords that admins are interested in.
    #
    entities = yield db.multiget_slice([myOrgId, myId], "entities", ['basic', 'admins'])
    entities = utils.multiSuperColumnsToDict(entities)
    orgAdmins = entities.get(myOrgId, {}).get('admins', {}).keys()
    if orgAdmins:
        text = ''
        monitoredFields = getattr(plugin, 'monitoredFields', {})
        for superColumnName in monitoredFields:
            for columnName in monitoredFields[superColumnName]:
                if columnName in conv[superColumnName]:
                    text = " ".join([text, conv[superColumnName][columnName]])
        matchedKeywords = yield utils.watchForKeywords(myOrgId, text)

        if matchedKeywords:
            reviewOK = utils.getRequestArg(request, "_review") == "1"
            if reviewOK:
                # Add conv to list of items that matched this keyword
                # and notify the administrators about it.
                for keyword in matchedKeywords:
                    yield db.insert(myOrgId+":"+keyword, "keywordItems", convId,
                                    conv['meta']['uuid'])
                    yield notifications.notify(orgAdmins, ':KW:'+keyword,
                                               myId, entities=entities)
            else:
                # This item contains a few keywords that are being monitored
                # by the admin and cannot be posted unless reviewOK is set.
                defer.returnValue((None, None, matchedKeywords))

    #
    # Save the new item to database and index it.
    #
    yield db.batch_insert(convId, "items", conv)
    for attachmentId in attachments:
        timeuuid, fid, name, size, ftype  = attachments[attachmentId]
        val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
        yield db.insert(convId, "item_files", val, timeuuid, attachmentId)

    yield files.pushfileinfo(myId, myOrgId, convId, conv)
    search.solr.updateItemIndex(convId, conv, myOrgId)

    #
    # Push item to feeds and userItems
    #
    timeUUID = conv["meta"]["uuid"]
    convACL = conv["meta"]["acl"]
    deferreds = []
    responseType = 'I'

    # Push to feeds
    d1 = feed.pushToFeed(myId, timeUUID, convId, None,
                         responseType, convType, myId, myId)
    d2 = feed.pushToOthersFeed(myId, myOrgId, timeUUID, convId, None, convACL,
                               responseType, convType, myId)
    deferreds.extend([d1, d2])

    # Save in user items.
    userItemValue = ":".join([responseType, convId, convId, convType, myId, ''])
    d = db.insert(myId, "userItems", userItemValue, timeUUID)
    deferreds.append(d)
    if plugins[convType].hasIndex:
        d = db.insert(myId, "userItems_%s"%(convType), userItemValue, timeUUID)
        deferreds.append(d)

    yield defer.DeferredList(deferreds)
    defer.returnValue((convId, conv, None))


@defer.inlineCallbacks
def _comment(request, myId, orgId, convId=None, richText=False):
    snippet, comment = utils.getTextWithSnippet(request, "comment",
                                                constants.COMMENT_PREVIEW_LENGTH,
                                                richText=richText)
    if not comment:
        raise errors.MissingParams([_("Comment")])

    # 0. Fetch conversation and see if I have access to it.
    (convId, conv) = yield utils.getValidItemId(request, "parent", myOrgId=orgId,
                                                myId=myId, itemId=convId)
    convType = conv["meta"].get("type", "status")
    me = yield db.get_slice(myId, "entities", ['basic'])
    me = utils.supercolumnsToDict(me)

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
    entities = yield db.multiget_slice([orgId, myId], "entities",
                                       ['basic', 'admins'])
    entities = utils.multiSuperColumnsToDict(entities)
    orgAdmins = entities.get(orgId, {}).get('admins', {}).keys()
    if orgAdmins:
        matchedKeywords = yield utils.watchForKeywords(orgId, comment)
        if matchedKeywords:
            reviewOK = utils.getRequestArg(request, '_review') == "1"
            if reviewOK:
                # Add item to list of items that matched this keyword
                # and notify the administrators about it.
                for keyword in matchedKeywords:
                    yield db.insert(orgId+":"+keyword, "keywordItems",
                                    itemId+":"+convId, timeUUID)
                    yield notifications.notify(orgAdmins, ':KW:'+keyword,
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
    search.solr.updateItemIndex(itemId, {'meta':meta}, orgId, conv=conv)
    items = {itemId: {'meta':meta}, convId: conv}
    defer.returnValue((itemId, convId, items, None))


@defer.inlineCallbacks
def deleteItem(request, itemId, item=None, parent=None):
    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username
    orgId = authinfo.organization

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

    if convId == itemId:
        # Delete from tagItems.
        if "tags" in item:
            for tagId in conv["tags"]:
                d = db.remove(tagId, "tagItems", itemUUID)
                deferreds.append(d)

        # Actually, delete the conversation.
        d1 = db.insert(itemOwnerId, 'deletedConvs', timestamp, itemId)
        d1.addCallback(lambda x: search.solr.delete(itemId))
        d1.addCallback(lambda x: files.deleteFileInfo(myId, orgId, itemId, item))
        deferreds.append(d1)

    else:
        if not parent:
            parent = yield db.get_slice(convId, "items", ["meta"])
            parent = utils.supercolumnsToDict(parent)

        convType = parent["meta"]["type"]
        convOwnerId = parent["meta"]["owner"]
        convACL = parent["meta"]["acl"]

        d1 = db.insert(convId, 'deletedConvs', timestamp, itemId)
        d2 = db.remove(convId, 'itemResponses', itemUUID)
        d2.addCallback(lambda x: db.get_count(convId, "itemResponses"))
        d2.addCallback(lambda x: db.insert(convId, 'items',\
                                 str(x), 'responseCount', 'meta'))
        d2.addCallback(lambda x: search.solr.delete(itemId))
        deferreds.extend([d1, d2])

        # Rollback changes to feeds caused by this comment
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

    yield defer.DeferredList(deferreds)


# Expects all the basic arguments as well as some information
# about the comments and likes to be available in kwargs.
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
        followers = yield db.get_slice(convId, "items", super_column="followers")
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
    # XXX: Entities generally contains a map of userId => {Basic: Data}
    #      In this case it will contain userId => data directly.
    notify_d = db.multiget_slice(toFetchEntities, "entities", ["basic"]) \
                        if recipients else defer.succeed([])
    def _gotEntities(cols):
        entities = utils.multiSuperColumnsToDict(cols)
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

        convId, conv, keywords = yield _createNewItem(request, myId, args['orgId'])
        if keywords:
            block = getBlock('item.mako', 'requireReviewDlg', keywords=keywords)
            request.write('$$.convs.reviewRequired(%s);' % json.dumps(block));
            return

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
        itemId, convId, items, keywords = yield _comment(request, myId, orgId)
        if keywords:
            block = getBlock('item.mako', 'requireReviewDlg', keywords=keywords, convId=convId)
            request.write('$$.convs.reviewRequired(%s, "%s");' % (json.dumps(block), convId));
            return

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
            d = deleteItem(request, itemId, item, conv)
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


    @defer.inlineCallbacks
    def _renderReportDialog(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        itemId, item = yield utils.getValidItemId(request, "id")
        args = {}

        itemType = item["meta"].get("type")

        args['title'] = _("Report this %s") %itemType
        args['convId'] = itemId

        yield renderScriptBlock(request, "item-report.mako", "report_dialog", False,
                                "#report-dlg-%s"%(itemId), "set", **args)


    @defer.inlineCallbacks
    def _renderItemRoot(self, request):
        itemType = conv["meta"].get("type", None)

        owner = meta["owner"]

        args["entities"] = {}
        toFetchEntities = set()


        if script:
            if itemType != "feedback":
                d = renderScriptBlock(request, "item-report.mako", "conv_owner",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", **args)
            else:
                feedbackType = conv['meta']['subType']
                d = renderScriptBlock(request, "item-report.mako", "feedback_icon",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", args=[feedbackType])

            renderers.append(d)

        if renderers:
            yield defer.DeferredList(renderers)


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
            yield render(request, "item-report.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "item-report.mako", "layout",
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

        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        args["entities"].update(entities)
        args["ownerId"] = convOwner

        renderers = []
        if script:
            d = renderScriptBlock(request, "item.mako", "conv_root",
                        landing, "#conv-root-%s > .conv-summary" %(convId),
                        "set", **args)
            renderers.append(d)

            d = renderScriptBlock(request, "item-report.mako", 'conv_footer',
                                  landing, '#item-footer-%s' % convId,
                                  'set', **args)
            renderers.append(d)

            if convType != "feedback":
                d = renderScriptBlock(request, "item.mako", "conv_owner",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", **args)
            else:
                feedbackType = conv['meta']['subType']
                d = renderScriptBlock(request, "item.mako", "feedback_icon",
                                      landing, "#conv-avatar-%s" % convId,
                                      "set", args=[feedbackType])

            renderers.append(d)

        d = self._renderReportResponses(request, convId, convMeta, args)
        renderers.append(d)

        if renderers:
            yield defer.DeferredList(renderers)

        if not script:
            yield render(request, "item-report.mako", **args)


    @defer.inlineCallbacks
    def _renderReportResponses(self, request, convId, convMeta, args):
        reportId = convMeta.get('reportId', None)
        args['convMeta'] = convMeta
        script = args["script"]
        myId = args["myId"]
        landing = not self._ajax

        if script:
            yield renderScriptBlock(request, "item-report.mako", "item_report",
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
                yield renderScriptBlock(request, "item-report.mako", 'report_comments',
                                        landing, '#report-comments', 'set', **args)


    @defer.inlineCallbacks
    def _submitReport(self, request, action):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        snippet, comment = utils.getTextWithSnippet(request, "comment",
                                            constants.COMMENT_PREVIEW_LENGTH)
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
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        entities.update({myId: args["me"]})

        if myId == convOwnerId:
            if action not in ["accept", "repost"]:
                raise errors.InvalidRequest(_('Invalid action was performed on the report'))

            convReport = {"reportStatus": action}
            yield db.batch_insert(convId, "items", {"meta": convReport})

            if action == "accept":
                # Owner removed the comment. Delete the item from his feed
                yield deleteItem(request, convId)
                request.write("$$.fetchUri('/feed');")
                request.write("$$.alerts.info('%s')" %_("Your item has been deleted"))
                request.finish()
            else:
                # Owner posted a reply, so notify reporter of the same
                yield _notify("RFC", convId, timeUUID, convType=convType,
                               convOwnerId=convOwnerId, myId=myId, entities=entities,
                               me=args["me"], reportedBy=convMeta["reportedBy"])
        else:
            if action not in ["report", "repost", "reject"]:
                raise errors.InvalidRequest(_('Invalid action was performed on the report'))

            if isNewReport:
                # Update Existing Item Information with Report Meta
                newACL = pickle.dumps({"accept":{"users":[convOwnerId, myId]}})
                convReport = {"reportedBy":myId, "reportId":reportId,
                              "reportStatus":"pending", "state":"flagged"}
                convMeta.update(convReport)
                yield db.batch_insert(convId, "items", {"meta": convReport})

                reportLink = """&#183;<a class="button-link" title="View Report" href="/item/report?id=%s"> View Report</a>""" % convId
                request.write("""$("#item-footer-%s").append('%s');""" %(convId, reportLink))
                yield _notify("FC", convId, timeUUID, convType=convType, entities=entities,
                              convOwnerId=convOwnerId, myId=myId, me=args["me"])
            else:
                if action == "repost":
                    # Remove the reportId key, so owner cannot post any comment
                    yield db.batch_remove({'items':[convId]},
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
                    yield db.batch_insert(reportId, "items", {"meta":oldReportMeta})

                    # Notify the owner that the report has been withdrawn
                    yield _notify("UFC", convId, timeUUID, convType=convType,
                                  convOwnerId=convOwnerId, myId=myId,
                                  entities=entities, me=args["me"])

                elif action  in ["reject", "report"]:
                    # Reporter rejects the comment by the owner or reports the
                    #  same item again.
                    convReport = {"reportStatus":"pending"}
                    yield _notify("RFC", convId, timeUUID, convType=convType,
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
            d =  self.renderItem(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == "responses":
                d = self._responses(request)
            if action == "likes":
                d = self._likes(request)
            if action == "report":
                d = self._renderReport(request)
            if action == "showReportDialog":
                d = self._renderReportDialog(request)

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

        if segmentCount == 2 and request.postpath[0] == "report":
            action = request.postpath[1]
            availableReportActions = ["report", "repost", "accept", "reject"]
            if action in availableReportActions:
                d = self._submitReport(request, action)

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
