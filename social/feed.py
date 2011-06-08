import time
import uuid

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base, plugins, _, __
from social.isocial     import IAuthInfo
from social.relations   import Relation
from social.template    import render, renderDef, renderScriptBlock
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE
from social.logging     import profile, dump_args

@defer.inlineCallbacks
def deleteUserFeed(userId, itemType, tuuid):
    yield Db.remove(userId, "userItems", tuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield Db.remove(userId, "userItems_"+ itemType, tuuid)

@defer.inlineCallbacks
def deleteFeed(userId, itemId, convId, itemType, acl, convOwner,
                responseType, others=None, tagId='', deleteAll=False):

    """
    wrapper around deleteFromFeed&deleteFromOthersFeed
    """

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
    cols = yield Db.get_slice(userId, "feedItems",
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

            yield Db.remove(userId, "feedItems", tuuid, convId)
            if latest == tuuid:
                yield Db.remove(userId, "feed", tuuid)
                if second:
                    yield Db.insert(userId, "feed", convId, second)
            if pseudoFeedTime:
                yield Db.remove(userId, "feedItems", super_column=convId)
                yield Db.remove(userId, "feed", pseudoFeedTime)
            if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                yield Db.remove(userId, "feed_"+itemType, tuuid)

            break


@profile
@defer.inlineCallbacks
@dump_args
def deleteFromOthersFeed(userId, itemId, convId, itemType, acl,
                         convOwner, responseType, others=None, tagId=''):
    if not others:
        others = yield utils.expandAcl(userId, acl, convOwner)
    for key in others:
        yield deleteFromFeed(key, itemId, convId, itemType,
                             userId, responseType, tagId=tagId )


@profile
@defer.inlineCallbacks
@dump_args
def pushToOthersFeed(userKey, timeuuid, itemKey, parentKey,
                     acl, responseType, itemType, convOwner,
                     others=None, tagId='', entities=None):
    if not others:
        others = yield utils.expandAcl(userKey, acl, convOwner)
    for key in others:
        yield pushToFeed(key, timeuuid, itemKey, parentKey,
                         responseType, itemType, convOwner,
                         userKey, tagId, entities)


@profile
@defer.inlineCallbacks
@dump_args
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
                itemType, convOwner=None, commentOwner=None, tagId='',
                entities=None):
    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner

    yield Db.insert(userKey, "feed", parentKey, timeuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield Db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)

    yield updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                               responseType, convOwner, commentOwner, tagId,
                               entities)


@profile
@defer.inlineCallbacks
@dump_args
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                        responseType, convOwner, commentOwner, tagId='',
                        entities=None):

    if not entities:
        entities = [commentOwner]
    else:
        entities.extend([commentOwner])
    entities = ",".join(entities)

    feedItemValue = ":".join([responseType, commentOwner, itemKey, entities, tagId])
    tmp, oldest, latest = {}, None, None

    cols = yield Db.get_slice(userKey, "feedItems",
                              super_column = parentKey, reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)

    for tuuid, val in cols.items():
        if tuuid == timeuuid:
            #trying to update feedItems more than once, don't update
            defer.returnValue(None)
        rtype = val.split(':')[0]
        if rtype not in  ('!', 'I'):
            tmp.setdefault(val.split(':')[0], []).append(tuuid)
            oldest = tuuid
        if rtype != "!" and not latest:
            #to prevent duplicate, feed should have only one entry of convId
            latest = tuuid
            yield Db.remove(userKey, "feed", tuuid)

    totalItems = len(cols)
    noOfItems = len(tmp.get(responseType, []))

    if noOfItems == MAXFEEDITEMSBYTYPE:
        oldest = tmp[responseType][noOfItems-1]

    if noOfItems == MAXFEEDITEMSBYTYPE or totalItems == MAXFEEDITEMS:
        yield Db.remove(userKey, "feedItems", oldest, parentKey)
        yield Db.remove(userKey, "feed", oldest)
        if plugins.has_key(itemType) and plugins[itemType].hasIndex:
            yield Db.remove(userKey, "feed_"+itemType, oldest)

    if totalItems == 0 and responseType != 'I':
        value = ":".join(["!", convOwner, parentKey, ""])
        tuuid = uuid.uuid1().bytes
        yield Db.batch_insert(userKey, "feedItems", {parentKey:{tuuid:value}})

    yield Db.batch_insert(userKey, "feedItems",
                          {parentKey:{timeuuid: feedItemValue}})


#
# getFeedItems: Generic function to fetch items to be displayed as a feed
#  - Checks ACLs (based on current user) on all the items in the feed but
#    does not verify if the user has access to the feed
#  - Unless feedItemsId is explicitly given context will always be based on
#    the currently logged in user.
#  - Use feedItemsId to establish context of another user - may be used for
#    administration purposes or when visiting other user's profile
#  - If getFn is given, it is called to fetch the list of ids from the Db.
#
@profile
@defer.inlineCallbacks
@dump_args
def getFeedItems(request, feedId=None, feedItemsId=None, convIds=None,
                 getFn=None, start='', count=10, getReason=True):
    toFetchItems = set()    # Items and entities that need to be fetched
    toFetchEntities = set() #
    toFetchTags = set()     #

    items = {}              # Fetched items, entities and tags
    entities = {}           #
    tags = {}               #

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

    relation = Relation(myId, [])
    relationsFetched = False
    relations_d = defer.DeferredList([relation.initFriendsList(),
                                      relation.initGroupsList()])

    # Filter conversations based on ACL, delete status etc;
    @defer.inlineCallbacks
    def fetchAndFilterConvs(ids, count):
        retIds = []
        if not ids:
            defer.returnValue(retIds)

        cols = yield Db.multiget_slice(ids, "items", ["meta", "tags"])
        items.update(utils.multiSuperColumnsToDict(cols))
        checkAcl = utils.checkAcl

        # Wait till user relations are fetched
        yield relations_d

        # Filter the items (checkAcl only for conversations)
        for convId in ids:
            if convId not in items:
                continue
            meta = items[convId]["meta"]
            if "deleted" in meta:
                continue
            if checkAcl(myId, meta["acl"], meta["owner"], relation, myOrgId):
                retIds.append(convId)
                if len(retIds) == count:
                    break

        defer.returnValue(retIds)

    # Fetch and process feed items
    reasonUserIds = {}
    reasonTagId = {}
    reasonTmpl = {}
    @defer.inlineCallbacks
    def fetchFeedItems(ids):
        rawFeedItems = yield Db.get_slice(feedItemsId, "feedItems", ids) \
                                            if ids else defer.succeed([])
        for conv in rawFeedItems:
            convId = conv.super_column.name
            updates = conv.super_column.columns
            mostRecentItem = None
            tagId = None
            responseUsers = []
            answerUsers = []
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

                if not getReason:
                    if x in ["C", "Q"]:
                        responses[convId].append(item)
                        toFetchItems.add(item)
                    elif x == "L" and convId != item:
                        if entities:
                            responses[convId].append(item)
                            toFetchItems.add(item)
                    elif x == "L":
                        likes[convId].append(user)

                elif x in ["C", "Q"]:
                    if x == "C":
                        responseUsers.append(user)
                    elif x == 'Q':
                        answerUsers.append(user)
                    responses[convId].append(item)
                    mostRecentItem = update
                    toFetchItems.add(item)
                elif x == "L" and convId == item:
                    likes[convId].append(user)
                    mostRecentItem = update
                elif x == "L":
                    mostRecentItem = update
                    if entities:
                        toFetchItems.add(item)
                        if item not in toFetchItems:
                            responses[convId].append(item)
                elif x == "T":
                    mostRecentItem = update
                    if len(update) > 4 and update[4]:
                        tagId = update[4]
                        toFetchTags.add(tagId)
                elif x == "I":
                    mostRecentItem = update

            if mostRecentItem:
                (x, userId, itemId) = mostRecentItem[0:3]
                if x == "C":
                    reasonUserIds[convId] = set(responseUsers)
                    reasonTmpl[convId] = ["%s commented on %s's %s",
                                          "%s and %s commented on %s's %s",
                                          "%s, %s and %s commented on %s's %s"]\
                                         [len(reasonUserIds[convId])-1]
                elif x == 'Q':
                    reasonUserIds[convId] = set(answerUsers)
                    reasonTmpl[convId] = ["%s answered %s's %s",
                                          "%s and %s answered %s's %s",
                                          "%s, %s and %s answered %s's %s"]\
                                         [len(reasonUserIds[convId])-1]

                elif x == "L" and itemId == convId:
                    reasonUserIds[convId] = set(likes[convId])
                    reasonTmpl[convId] = ["%s liked %s's %s",
                                          "%s and %s liked %s's %s",
                                          "%s, %s and %s liked %s's %s"]\
                                         [len(reasonUserIds[convId])-1]
                elif x == "L":
                    reasonUserIds[convId] = set([userId])
                    reasonTmpl[convId] = "%s liked a comment on %s's %s"
                elif x == "T":
                    reasonUserIds[convId] = set([userId])
                    reasonTagId[convId] = tagId
                    reasonTmpl[convId] = "%s added %s on %s's %s"

    # If we don't have a list of conversations,
    # fetch the list of either the given feedId or from the user's feed
    if not convIds:
        feedId = feedId or myId
        nextPageStart = None
        keysFromFeed = []
        convIds = []

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

            # Fetch user's feed when getFn isn't given.
            else:
                results = yield Db.get_slice(feedId, "feed", count=fetchCount,
                                          start=fetchStart, reverse=True)
                for col in results:
                    value = col.column.value
                    if value not in allFetchedConvIds:
                        fetchedConvIds.append(value)
                        allFetchedConvIds.append(value)
                        keysFromFeed.append(col.column.name)

            if not keysFromFeed:
                break

            fetchStart = keysFromFeed[-1]
            feedItems_d.append(fetchFeedItems(fetchedConvIds))
            filteredConvIds = yield fetchAndFilterConvs(fetchedConvIds, count)
            convIds.extend(filteredConvIds)

            if len(results) < fetchCount:
                break

        if len(keysFromFeed) > count:   # We have more items than count
            nextPageStart = utils.encodeKey(keysFromFeed[count])
            convIds = convIds[0:count]
        elif len(results) == fetchCount:   # We got duplicate items in feed
            nextPageStart = utils.encodeKey(keysFromFeed[-1])
            convIds = convIds[0:-1]
    else:
        convIds = fetchAndFilterConvs(convIds)

    # We don't have any conversations to display!
    if not convIds:
        defer.returnValue({"conversations": []})

    # We now have a filtered list of conversations that can be displayed
    # Let's wait till all the feed items have been fetched and processed
    yield defer.DeferredList(feedItems_d)

    # Fetch the required entities, tags and items to finish the job!
    items_d = Db.multiget_slice(toFetchItems, "items", ["meta"])

    for convId in convIds:
        conv = items[convId]
        toFetchEntities.add(conv["meta"]["owner"])
        if "target" in conv["meta"]:
            toFetchEntities.add(conv["meta"]["target"])
        toFetchTags.update(conv.get("tags",{}).keys())

    entities_d = Db.multiget_slice(toFetchEntities, "entities", ["basic"])
    tags_d = Db.get_slice(myOrgId, "orgTags", toFetchTags) \
                                if toFetchTags else defer.succeed([])

    myLikes_d = Db.multiget(toFetchItems.union(convIds), "itemLikes", myId)

    # Extra data that is required to render special items
    # We already fetched the conversation items, plugins merely
    # add more data to the already fetched items
    extraData_d = []
    data["items"] = items
    for convId in convIds:
        itemType = items[convId]["meta"]["type"]
        if itemType in plugins:
            try:
                d = plugins[itemType].fetchData(data, convId)
                extraData_d.append(d)
            except:
                pass

    # Results of previously initiated fetches (items, tags, entities, likes)
    fetchedItems = yield items_d
    items.update(utils.multiSuperColumnsToDict(fetchedItems))

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
            template = reasonTmpl.get(convId, None)
            conv = items[convId]
            ownerId = conv["meta"]["owner"]

            if template:
                vals = [userName(id, entities[id], "conv-user-cause")\
                        for id in reasonUserIds[convId]]
                if convId in reasonTagId:
                    tagId = reasonTagId[convId]
                    tagname = tags[tagId]["title"]
                    vals.append("<a class='ajax' href='/tags?id=%s'>%s</a>"%(tagId, tagname))
                vals.append(userName(ownerId, entities[ownerId]))
                itemType = conv["meta"]["type"]
                vals.append(itemLink(convId, itemType))
                reasonStr[convId] = _(template) % tuple(vals)

    results = yield defer.DeferredList(extraData_d)
    # TODO: Fetch any extra entities that the plugins might ask for!

    data.update({"entities": entities, "responses": responses, "likes": likes,
                 "myLikes": myLikes, "conversations": convIds, "tags": tags,
                 "nextPageStart": nextPageStart, "reasonStr": reasonStr})
    defer.returnValue(data)


def _feedFilter(request, feedId, itemType, start='', count=10):

    @defer.inlineCallbacks
    def getFn(start='', count=12):
        cf = "feed_%s"%(itemType)
        items = yield Db.get_slice(feedId, cf, start=start, count=count)
        defer.returnValue(utils.columnsToDict(items, ordered=True))
    return getFeedItems(request, getFn= getFn, start=start)


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

        landing = not self._ajax
        myOrgId = args["orgKey"]

        args["feedTitle"] = _("News Feed")
        args["menuId"] = "feed"

        if entityId:
            entity = yield Db.get_slice(entityId, "entities", ["basic", "admins"])
            entity = utils.supercolumnsToDict(entity)
            entityType = entity["basic"]['type']

            if entityType == "org":
                if entityId != myOrgId:
                    errors.InvalidRequest()
                args["feedTitle"] = _("Company Feed: %s") % entity["basic"]["name"]
                args["menuId"] = "org"
            elif entityType == "group":
                args["feedTitle"] = _("Group Feed: %s") % entity["basic"]["name"]
                args["groupAdmins"] = entity["admins"]
                args["groupId"] = entityId
                args["menuId"] = "groups"
            elif entityId != myId:
                errors.InvalidRequest()

        feedId = entityId or myId
        args["feedId"] = feedId

        if script and landing:
            yield render(request, "feed.mako", **args)
        elif script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        elif script and "feedTitle" in args:
            yield renderScriptBlock(request, "feed.mako", "feed_title",
                                    landing, "#title", "set", True,
                                    handlers={"onload": "$$.menu.selectItem('%s')"%args["menuId"]}, **args)

        start = utils.getRequestArg(request, "start") or ''

        if script:
            handlers = {}
            if "groupId" in args:
                groupName = args["feedTitle"].split(":", 1)[1].strip()
                groupId = args['feedId']
                handlers["onload"] = "$$.acl.switchACL('sharebar-acl', 'group','%s', '%s')" %(groupId, groupName)

            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing, "#share-block", "set", handlers=handlers, **args)
            yield self._renderShareBlock(request, "status")

        if itemType and itemType in plugins and plugins[itemType].hasIndex:
            feedItems = yield _feedFilter(request, feedId, itemType, start)
        else:
            feedItems = yield getFeedItems(request, feedId=feedId, start=start)
        args.update(feedItems)
        args['itemType']=itemType
        cols = yield Db.get_slice(myId, "latestNotifications")
        cols = utils.supercolumnsToDict(cols)
        counts = dict([(key, len(cols[key])) for key in cols])

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                    "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)
            yield renderScriptBlock(request, "feed.mako", "groupLinks",
                                    landing, "#group-links", "set",  **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)


    # The client has scripts and this is an ajax request
    @defer.inlineCallbacks
    def _renderMore(self, request, start, entityId, itemType=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
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


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == "more":
            entityId = utils.getRequestArg(request, "id")
            start = utils.getRequestArg(request, "start") or ""
            itemType = utils.getRequestArg(request, 'type')
            d = self._renderMore(request, start, entityId, itemType)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])

        return self._epilogue(request, d)
