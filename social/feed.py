import time
import uuid

from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, plugins, _, __, errors, people
from social.isocial     import IAuthInfo
from social.relations   import Relation
from social.template    import render, renderDef, renderScriptBlock
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE
from social.constants   import SUGGESTION_PER_PAGE
from social.logging     import profile, dump_args, log

@defer.inlineCallbacks
def deleteUserFeed(userId, itemType, tuuid):
    yield db.remove(userId, "userItems", tuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield db.remove(userId, "userItems_"+itemType, tuuid)


@defer.inlineCallbacks
def deleteFeed(userId, itemId, convId, itemType, acl, convOwner,
               responseType, others=None, tagId='', deleteAll=False):
    #
    # Wrapper around deleteFromFeed and deleteFromOthersFeed
    #
    yield deleteFromFeed(userId, itemId, convId, itemType,
                         userId, responseType, tagId )
    if deleteAll:
        yield deleteFromOthersFeed(userId, itemId, convId, itemType, acl,
                                   convOwner, responseType, others, tagId)


@profile
@defer.inlineCallbacks
@dump_args
def deleteFromFeed(userId, itemId, convId, itemType,
                   itemOwner, responseType, tagId=''):
    # fix: itemOwner is either the person who owns the item
    #       or person who liked the item. RENAME the variable.
    cols = yield db.get_slice(userId, "feedItems",
                              super_column=convId, reverse=True)

    noOfItems = len(cols)
    latest, second, pseudoFeedTime = None, None, None
    for col in cols:
        tuuid = col.column.name
        val = col.column.value
        rtype, poster, key =  val.split(":")[0:3]
        if latest and not second and rtype != "!":
            second = tuuid
        if not latest and rtype != "!":
            latest = tuuid
        if noOfItems == 2 and rtype == "!":
            pseudoFeedTime = tuuid

    cols = utils.columnsToDict(cols)

    for tuuid, val in cols.items():
        vals = val.split(":")
        rtype, poster, key =  val.split(":")[0:3]
        tag = ''
        if len(vals) == 5 and vals[4]:
            tag = vals[4]
        if rtype == responseType and \
            (rtype == "T" or poster == itemOwner) and \
            key == itemId and tagId == tag:
            # anyone can untag

            yield db.remove(userId, "feedItems", tuuid, convId)
            if latest == tuuid:
                yield db.remove(userId, "feed", tuuid)
                if second:
                    yield db.insert(userId, "feed", convId, second)
            if pseudoFeedTime:
                yield db.remove(userId, "feedItems", super_column=convId)
                yield db.remove(userId, "feed", pseudoFeedTime)
            if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                yield db.remove(userId, "feed_"+itemType, tuuid)

            break


@profile
@defer.inlineCallbacks
@dump_args
def deleteFromOthersFeed(userId, itemId, convId, itemType, acl,
                         convOwner, responseType, others=None, tagId=''):
    if not others:
        others = yield utils.expandAcl(userId, acl, convId, convOwner)

    for key in others:
        yield deleteFromFeed(key, itemId, convId, itemType,
                             userId, responseType, tagId=tagId)


@profile
@defer.inlineCallbacks
@dump_args
def pushToOthersFeed(userKey, timeuuid, itemKey, parentKey, acl,
                     responseType, itemType, convOwner, others=None,
                     tagId='', entities=None, promoteActor=True):
    if not others:
        others = yield utils.expandAcl(userKey, acl, parentKey, convOwner)

    for key in others:
        promote = (userKey != key) or (promoteActor)
        yield pushToFeed(key, timeuuid, itemKey, parentKey,
                         responseType, itemType, convOwner,
                         userKey, tagId, entities, promote=promote)


@profile
@defer.inlineCallbacks
@dump_args
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
               itemType, convOwner=None, commentOwner=None, tagId='',
               entities=None, promote=True):
    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner

    # Get this conversation to the top of the feed only if promote is set
    if promote:
        yield db.insert(userKey, "feed", parentKey, timeuuid)
        if plugins.has_key(itemType) and plugins[itemType].hasIndex:
            yield db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)

    yield updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                              responseType, convOwner, commentOwner, tagId,
                              entities, promote)


@profile
@defer.inlineCallbacks
@dump_args
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                        responseType, convOwner, commentOwner, tagId,
                        entities, promote):
    if not entities:
        entities = [commentOwner]
    else:
        entities.extend([commentOwner])
    entities = ",".join(entities)

    feedItemValue = ":".join([responseType, commentOwner, itemKey, entities, tagId])
    tmp, oldest, latest = {}, None, None

    cols = yield db.get_slice(userKey, "feedItems",
                              super_column=parentKey, reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)

    feedKeys = []
    userFeedItems = []
    userFeedItemsByType = {}
    for tuuid, val in cols.items():
        # Bailout if we already know about this update.
        if tuuid == timeuuid:
            defer.returnValue(None)

        rtype = val.split(':')[0]
        if rtype not in  ('!', 'I'):
            tmp.setdefault(rtype, []).append(tuuid)
            if val.split(':')[1] == userKey:
                userFeedItems.append(tuuid)
                userFeedItemsByType.setdefault(rtype, []).append(tuuid)
            oldest = tuuid

        feedKeys.append(tuuid)

    # Remove older entries of this conversation from the feed
    # only if a new one was added before this function was called.
    if promote and feedKeys:
        yield db.batch_remove({'feed': [userKey]}, names=feedKeys)

    totalItems = len(cols)
    noOfItems = len(tmp.get(responseType, []))

    if noOfItems == MAXFEEDITEMSBYTYPE:
        if (len(userFeedItemsByType.get(responseType, {})) == MAXFEEDITEMSBYTYPE  and not promote)\
           or (tmp[responseType][noOfItems-1] not in userFeedItemsByType.get(responseType, {}) \
               and len(userFeedItemsByType.get(responseType, {})) == MAXFEEDITEMSBYTYPE-1 and not promote):
             oldest = userFeedItemsByType[responseType][noOfItems-2]
        else:
            oldest = tmp[responseType][noOfItems-1]

    if ((len(userFeedItems)== MAXFEEDITEMS-1 and not promote) or \
       (oldest not in userFeedItems and len(userFeedItems) == MAXFEEDITEMS-2 and not promote)):

        oldest = userFeedItems[-2]

    if noOfItems == MAXFEEDITEMSBYTYPE or totalItems == MAXFEEDITEMS:
        yield db.remove(userKey, "feedItems", oldest, parentKey)
        if plugins.has_key(itemType) and plugins[itemType].hasIndex:
            yield db.remove(userKey, "feed_"+itemType, oldest)

    if totalItems == 0 and responseType != 'I':
        value = ":".join(["!", convOwner, parentKey, ""])
        tuuid = uuid.uuid1().bytes
        yield db.batch_insert(userKey, "feedItems", {parentKey:{tuuid:value}})

    yield db.batch_insert(userKey, "feedItems",
                          {parentKey:{timeuuid: feedItemValue}})


#
# getFeedItems: Generic function to fetch items to be displayed as a feed
#  - Checks ACLs (based on current user) on all the items in the feed but
#    does not verify if the user has access to the feed
#  - Unless feedItemsId is explicitly given context will always be based on
#    the currently logged in user.
#  - Use feedItemsId to establish context of another user - may be used for
#    administration purposes or when visiting other user's profile
#  - If getFn is given, it is called to fetch the list of ids from the db.
#
# Filter conversations based on ACL, delete status etc;
@defer.inlineCallbacks
def fetchAndFilterConvs(ids, count, relation, items, myId, myOrgId):
    retIds = []
    deleted = set()
    if not ids:
        defer.returnValue((retIds, deleted))

    cols = yield db.multiget_slice(ids, "items", ["meta", "tags", "attachments"])
    items.update(utils.multiSuperColumnsToDict(cols))
    checkAcl = utils.checkAcl

    # Filter the items (checkAcl only for conversations)
    for convId in ids:
        if convId not in items:
            log.info('Missing item: ', convId)
            continue
        meta = items.get(convId, {}).get("meta", {})
        if not meta:
            continue
        if "deleted" in meta:
            deleted.add(convId)
            continue
        if checkAcl(myId, meta["acl"], meta["owner"], relation, myOrgId):
            retIds.append(convId)
            if len(retIds) == count:
                break

    defer.returnValue((retIds, deleted))

@profile
@defer.inlineCallbacks
@dump_args
def getFeedItems(request, feedId=None, feedItemsId=None, convIds=None,
                 getFn=None, cleanFn=None, start='', count=10, getReason=True):
    toFetchItems = set()    # Items and entities that need to be fetched
    toFetchEntities = set() #
    toFetchTags = set()     #

    items = {}              # Fetched items, entities and tags
    entities = {}           #
    tags = {}               #

    deleted = set()         # List of items that were deleted

    responses = {}          # Cached data of item responses and likes
    likes = {}              #
    myLikes = {}

    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username
    myOrgId = authinfo.organization

    data = {"myKey": myId}  # Passed to plugins and is ultimately returned

    feedItemsId = feedItemsId or myId
    feedItems_d = []        # List of deferred used to fetch feedItems
    rawFeedItems = {}       # Feed items - fetched in parallel
    allFetchedConvIds = []  # List of all convIds considered for filtering
    itemsFromFeed = {}      # All the key-values retrieved from feed

    relation = Relation(myId, [])
    relationsFetched = False
    yield relation.initGroupsList()

    # Fetch and process feed items
    reasonUserIds = {}
    reasonTagId = {}
    reasonTmpl = {}
    @defer.inlineCallbacks
    def fetchFeedItems(ids):
        rawFeedItems = yield db.get_slice(feedItemsId, "feedItems", ids) \
                                            if ids else defer.succeed([])
        for conv in rawFeedItems:
            convId = conv.super_column.name
            updates = conv.super_column.columns
            mostRecentItem = None
            tagId = None
            responseUsers = []
            responses[convId] = []
            likes[convId] = []

            for update in updates:
                update = update.value.split(':')
                if len(update) < 4:
                    continue

                (x, user, item, entities) = update[0:4]
                toFetchEntities.add(user)
                if entities:
                    toFetchEntities.update(entities.split(","))

                # If I am the cause for any update ensure that my
                # name is not listed in the reason string.
                myAction = True if user == myId else False

                if not getReason:
                    if x in ["C", "Q"]:
                        if item not in responses.get(convId, []):
                            responses[convId].append(item)
                            toFetchItems.add(item)
                    elif x == "L" and convId != item:
                        if entities and item not in responses.get(convId, []):
                            responses[convId].append(item)
                            toFetchItems.add(item)
                    elif x == "L":
                        likes[convId].insert(0, user)

                elif x in ("C", "Q"):
                    if not myAction:
                        responseUsers.insert(0, user)
                    responses[convId].append(item)
                    toFetchItems.add(item)
                elif x == "L" and convId == item:
                    if not myAction:
                        likes[convId].insert(0, user)
                elif x == "L":
                    if entities:
                        toFetchItems.add(item)
                        if item not in toFetchItems:
                            responses[convId].append(item)
                elif x == "T":
                    if len(update) > 4 and update[4]:
                        tagId = update[4]
                        toFetchTags.add(tagId)

                # Ignore my action when deciding on the most recent
                # update that happened on this item.
                if getReason and not myAction:
                    mostRecentItem = update

            if mostRecentItem:
                (x, userId, itemId) = mostRecentItem[0:3]
                if x == "C":
                    reasonUserIds[convId] = utils.uniqify(responseUsers)
                    reasonTmpl[convId] = [["%(user0)s commented on your %(itemType)s",
                                           "%(user0)s commented on %(owner)s's %(itemType)s"],
                                          ["%(user0)s and %(user1)s commented on your %(itemType)s",
                                           "%(user0)s and %(user1)s commented on %(owner)s's %(itemType)s"],
                                          ["%(user0)s, %(user1)s and %(user2)s commented on your %(itemType)s",
                                           "%(user0)s, %(user1)s and %(user2)s commented on %(owner)s's %(itemType)s"]]\
                                         [len(reasonUserIds[convId])-1]
                elif x == 'Q':
                    reasonUserIds[convId] = utils.uniqify(responseUsers)
                    reasonTmpl[convId] = [["%(user0)s answered your %(itemType)s",
                                          "%(user0)s answered %(owner)s's %(itemType)s"],
                                          ["%(user0)s and %(user1)s answered your %(itemType)s",
                                          "%(user0)s and %(user1)s answered %(owner)s's %(itemType)s"],
                                          ["%(user0)s, %(user1)s and %(user2)s answered your %(itemType)s",
                                          "%(user0)s, %(user1)s and %(user2)s answered %(owner)s's %(itemType)s"]]\
                                         [len(reasonUserIds[convId])-1]

                elif x == "L" and itemId == convId:
                    reasonUserIds[convId] = utils.uniqify(likes[convId])
                    reasonTmpl[convId] = [["%(user0)s liked your %(itemType)s",
                                           "%(user0)s liked %(owner)s's %(itemType)s"],
                                          ["%(user0)s and %(user1)s liked your %(itemType)s",
                                           "%(user0)s and %(user1)s liked %(owner)s's %(itemType)s"],
                                          ["%(user0)s, %(user1)s and %(user2)s liked your %(itemType)s",
                                           "%(user0)s, %(user1)s and %(user2)s liked %(owner)s's %(itemType)s"]]\
                                         [len(reasonUserIds[convId])-1]
                elif x == "L":
                    reasonUserIds[convId] = [userId]
                    reasonTmpl[convId] = [["%(user0)s liked a comment on your %(itemType)s",
                                           "%(user0)s liked a comment on %(owner)s's %(itemType)s"],
                                          ["%(user0)s and %(user1)s liked a comment on your %(itemType)s",
                                           "%(user0)s and %(user1)s liked a comment on %(owner)s's %(itemType)s"],
                                          ["%(user0)s, %(user1)s and %(user2)s liked a comment on your %(itemType)s",
                                           "%(user0)s, %(user1)s and %(user2)s liked a comment on %(owner)s's %(itemType)s"]]\
                                         [len(reasonUserIds[convId])-1]
                elif x == "T":
                    reasonUserIds[convId] = [userId]
                    reasonTagId[convId] = tagId
                    reasonTmpl[convId] = ["%(user0)s added %(tagName)s on your %(itemType)s",
                                          "%(user0)s added %(tagName)s on %(owner)s's %(itemType)s"]


    # If we don't have a list of conversations,
    # fetch the list of either the given feedId or from the user's feed
    nextPageStart = None
    if not convIds:
        feedId = feedId or myId
        keysFromFeed = []   # Sorted list of keys (used for paging)
        convIds = []        # List of convIds that will be displayed

        fetchStart = utils.decodeKey(start)
        fetchCount = count + 2
        while len(convIds) < count:
            fetchedConvIds = []

            # Use the getFn function if given.
            if getFn:
                results = yield getFn(start=fetchStart, count=fetchCount)
                for name, value in results.items():
                    if value not in allFetchedConvIds:
                        fetchedConvIds.append(value)
                        allFetchedConvIds.append(value)
                        keysFromFeed.append(name)
                        itemsFromFeed[name] = value

            # Fetch user's feed when getFn isn't given.
            else:
                results = yield db.get_slice(feedId, "feed", count=fetchCount,
                                              start=fetchStart, reverse=True)
                for col in results:
                    value = col.column.value
                    if value not in allFetchedConvIds:
                        fetchedConvIds.append(value)
                        allFetchedConvIds.append(value)
                        keysFromFeed.append(col.column.name)
                        itemsFromFeed[col.column.name] = value

            if not keysFromFeed:
                break

            fetchStart = keysFromFeed[-1]
            feedItems_d.append(fetchFeedItems(fetchedConvIds))
            (filteredConvIds, deletedIds) = yield fetchAndFilterConvs\
                        (fetchedConvIds, count, relation, items, myId, myOrgId)
            convIds.extend(filteredConvIds)
            deleted.update(deletedIds)

            if len(results) < fetchCount:
                break

        if len(keysFromFeed) > count:   # We have more items than count
            nextPageStart = utils.encodeKey(keysFromFeed[count])
            convIds = convIds[0:count]
        elif len(results) == fetchCount:   # We got duplicate items in feed
            nextPageStart = utils.encodeKey(keysFromFeed[-1])
            convIds = convIds[0:-1]
    else:
        (convIds, deletedIds) = yield fetchAndFilterConvs(convIds, count,
                                                relation, items, myId, myOrgId)
        if len(convIds) > count:
            nextPageStart = utils.encodeKey(convIds[count])
            convIds = convIds[0:count]
        if deletedIds:
            data["deleted"] = deletedIds

    # We don't have any conversations to display!
    if not convIds:
        defer.returnValue({"conversations": []})

    # Delete any convs that don't exist anymore from the feeds
    cleanup_d = []
    if deleted:
        if cleanFn:
            d1 = cleanFn(list(deleted))
        else:
            deleteKeys = []
            for key, value in itemsFromFeed.items():
                if value in deleted:
                    deleteKeys.append(key)

            d1 = db.batch_remove({'feed': [feedId]}, names=deleteKeys)

        d2 = db.batch_remove({'feedItems': [feedId]}, names=list(deleted))
        cleanup_d = [d1, d2]

    # We now have a filtered list of conversations that can be displayed
    # Let's wait till all the feed items have been fetched and processed
    yield defer.DeferredList(feedItems_d)

    # Fetch the required entities, tags and items to finish the job!
    items_d = db.multiget_slice(toFetchItems, "items", ["meta" ,"attachments"])

    for convId in convIds:
        conv = items[convId]
        toFetchEntities.add(conv["meta"]["owner"])
        if "target" in conv["meta"]:
            toFetchEntities.update(conv["meta"]["target"].split(','))
        toFetchTags.update(conv.get("tags",{}).keys())

    tags_d = db.get_slice(myOrgId, "orgTags", toFetchTags) \
                                if toFetchTags else defer.succeed([])

    myLikes_d = db.multiget(toFetchItems.union(convIds), "itemLikes", myId)

    # Extra data that is required to render special items
    # We already fetched the conversation items, plugins merely
    # add more data to the already fetched items
    data["items"] = items
    for convId in convIds:
        itemType = items[convId]["meta"]["type"]
        if itemType in plugins:
            try:
                entityIds = yield plugins[itemType].fetchData(data, convId)
                toFetchEntities.update(entityIds)
            except Exception, e:
                log.err(e)

    # Results of previously initiated fetches (items, tags, entities, likes)
    fetchedItems = yield items_d
    items.update(utils.multiSuperColumnsToDict(fetchedItems))

    entities_d = db.multiget_slice(toFetchEntities, "entities", ["basic"])
    fetchedEntities = yield entities_d
    entities.update(utils.multiSuperColumnsToDict(fetchedEntities))

    fetchedTags = yield tags_d
    tags.update(utils.supercolumnsToDict(fetchedTags))

    fetchedMyLikes = yield myLikes_d
    myLikes.update(utils.multiColumnsToDict(fetchedMyLikes))

    # Build the reason string (if required)
    reasonStr = {}
    userName = utils.userName
    itemLink = utils.itemLink
    if getReason:
        for convId in convIds:
            conv = items[convId]
            ownerId = conv["meta"]["owner"]
            template = reasonTmpl.get(convId, None)
            if template:
                template = template[0] if ownerId == myId else template[1]
                vals = dict([('user'+str(idx), userName(id, entities[id], "conv-user-cause"))\
                            for idx, id in enumerate(reasonUserIds[convId])])
                if convId in reasonTagId:
                    tagId = reasonTagId[convId]
                    tagname = tags[tagId]["title"]
                    vals['tagName'] = "<a class='ajax' href='/tags?id=%s'>%s</a>"%(tagId, tagname)
                vals["owner"] = userName(ownerId, entities[ownerId])
                vals["itemType"] = itemLink(convId, conv["meta"]["type"])
                reasonStr[convId] = _(template) % vals

    # Make sure that the cleanup has happened too
    yield defer.DeferredList(cleanup_d)

    data.update({"entities": entities, "responses": responses, "likes": likes,
                 "myLikes": myLikes, "conversations": convIds, "tags": tags,
                 "nextPageStart": nextPageStart, "reasonStr": reasonStr,
                 "reasonUserIds": reasonUserIds, "relations":relation})
    defer.returnValue(data)


def _feedFilter(request, feedId, itemType, start='', count=10):
    itemsFromFeed = {}
    cf = "feed_%s"%(itemType)

    @defer.inlineCallbacks
    def getFn(start='', count=12):
        items = yield db.get_slice(feedId, cf, start=start,
                                   count=count, reverse=True)
        items = utils.columnsToDict(items, ordered=True)
        itemsFromFeed.update(items)
        defer.returnValue(items)

    @defer.inlineCallbacks
    def cleanFn(convIds):
        deleteKeys = []
        for key, value in itemsFromFeed.items():
            if value in deleted:
                deleteKeys.append(key)
        yield db.batch_remove({cf: [feedId]}, names=deleteKeys)

    return getFeedItems(request, getFn=getFn, cleanFn=cleanFn, start=start)


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        itemType = utils.getRequestArg(request, 'type')
        entityId = utils.getRequestArg(request, 'id')
        start = utils.getRequestArg(request, "start") or ''

        landing = not self._ajax
        myOrgId = args["orgKey"]

        feedTitle = _("News Feed")
        menuId = "feed"

        if entityId:
            entity = yield db.get_slice(entityId, "entities", ["basic", "admins"])
            if not entity:
                raise errors.InvalidEntity("feed", entityId)

            entity = utils.supercolumnsToDict(entity)
            entityType = entity["basic"]['type']

            orgId = entity['basic']["org"] if entity['basic']["type"] != "org" else entityId

            if myOrgId != orgId:
                raise errors.EntityAccessDenied("organization", entityId)

            if entityType == 'org':
                menuId = "org"
                feedTitle = _("Company Feed: %s") % entity["basic"]["name"]
            elif entityType == 'group':
                log.info("group-feed should be handled by groups resource")
                request.redirect("/group?id=%s"%(entityId))
                defer.returnValue(None)
            else:
                if entityId != myId:
                    raise errors.EntityAccessDenied("user", entityId)

        feedId = entityId or myId
        args["feedTitle"] = feedTitle

        if script and landing:
            yield render(request, "feed.mako", **args)
            request.write('<script>$("#invite-form").html5form({messages: "en"})</script>')
        elif script and appchange:
            onload = '$("#invite-form").html5form({messages: "en"})'
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", handlers={'onload':onload}, **args)
        elif script and feedTitle:
            yield renderScriptBlock(request, "feed.mako", "feed_title",
                                    landing, "#title", "set", True,
                                    handlers={"onload": "$$.menu.selectItem('%s')"%(menuId)}, **args)

        if script:
            handlers = {}
            handlers["onload"] = handlers.get("onload", "") +\
                                 "$$.files.init('sharebar-attach');"
            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing, "#share-block", "set",
                                    handlers=handlers, **args)
            yield self._renderShareBlock(request, "status")

        if itemType and itemType in plugins and plugins[itemType].hasIndex:
            feedItems = yield _feedFilter(request, feedId, itemType, start)
        else:
            feedItems = yield getFeedItems(request, feedId=feedId, start=start)

        args.update(feedItems)

        args["feedId"] = feedId
        args["menuId"] = menuId
        args['itemType']=itemType

        suggestions, entities = yield people.get_suggestions(request,
                                                SUGGESTION_PER_PAGE, mini=True)
        args["suggestions"] = suggestions

        if "entities" not in args:
            args["entities"] = entities
        else:
            for entity in entities:
                if entity not in args["entities"]:
                    args["entities"][entity] = entities[entity]
        
        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                    "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)
            yield renderScriptBlock(request, "feed.mako", "_suggestions",
                                    landing, "#suggestions", "set", True, **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)


    # The client has scripts and this is an ajax request
    @defer.inlineCallbacks
    def _renderMore(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        entityId = utils.getRequestArg(request, "id")
        start = utils.getRequestArg(request, "start") or ""
        itemType = utils.getRequestArg(request, 'type')
        entity = yield db.get_slice(entityId, "entities", ["basic"])
        entity = utils.supercolumnsToDict(entity)
        if entity and entity["basic"].get("type", '') == "group":
            errors.InvalidRequest("group feed will not be fetched.")

        if itemType and itemType in plugins and plugins[itemType].hasIndex:
            feedItems = yield _feedFilter(request, entityId, itemType, start)
        else:
            feedItems = yield getFeedItems(request, feedId=entityId, start=start)
        args.update(feedItems)
        args["feedId"] = entityId
        args['itemType'] = itemType

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        yield renderScriptBlock(request, "feed.mako", "feed", False,
                                "#next-load-wrapper", "replace", True,
                                handlers={"onload": onload}, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    @defer.inlineCallbacks
    def _renderChooseAudience(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        onload = "$('form').html5form({messages: 'en'});"
        yield renderScriptBlock(request, "feed.mako", "customAudience", False,
                                "#custom-audience-dlg", "set", True,
                                handlers={"onload": onload}, **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0 or (segmentCount==1 and request.postpath[0]==''):
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == "more":
            d = self._renderMore(request)
        elif segmentCount == 1 and request.postpath[0] == "audience":
            d = self._renderChooseAudience(request)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])

        return self._epilogue(request, d)
