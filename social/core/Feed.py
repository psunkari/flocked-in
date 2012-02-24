
from twisted.internet   import defer
from twisted.plugin     import getPlugins

from social             import db, errors, utils, plugins
from social.relations   import Relation
from social.isocial     import IAuthInfo, IFeedUpdateType


_feedUpdatePlugins =  dict()
for plg in getPlugins(IFeedUpdateType):
    if not hasattr(plg, "disabled") or not plg.disabled:
        _feedUpdatePlugins[plg.updateType] = plg


@defer.inlineCallbacks
def get(auth, feedId=None, feedItemsId=None, convIds=None,
        getFn=None, cleanFn=None, start='', count=10, getReasons=True,
        forceCount=False, itemType=None):
    """Fetch data from feed represented by feedId. Returns a dictionary
    that has the items from feed, start of the next page and responses and
    likes that I know of.

    Keyword params:
    @auth -  An instance of AuthInfo representing the authenticated user
    @feedId -  Id of the feed from which the data is to be fetched
    @feedItemsId -  Id of the feed from with feed items must be fetched
    @convIds -  List of conversation id's to be used as feed
    @getFn -  Function that must be used to fetch items
    @cleanFn -  Function that must be used to clean items that don't exist
    @start -  Id of the item where the fetching must start
    @count - Number of items to fetch
    @getReasons - Add reason strings to the returned dictionary
    @forceCount - Try hard to get atleast count items from the feed
    """
    toFetchItems = set()    # Items and entities that need to be fetched
    toFetchEntities = set() #
    toFetchTags = set()     #

    items = {}              # Fetched items, entities and tags
    entities = {}           #
    tags = {}               #

    deleted = []            # List of items that were deleted
    deleteKeys = []         # List of keys that need to be deleted

    responses = {}          # Cached data of item responses and likes
    likes = {}              #
    myLikes = {}

    myId = auth.username
    orgId = auth.organization

    feedSource = "feed_%s" % itemType\
                        if itemType and itemType in plugins\
                                    and plugins[itemType].hasIndex\
                        else "feed"
    feedItemsId = feedItemsId or myId
    feedItems_d = []            # List of deferred used to fetch feedItems

    # Used for checking ACL
    relation = Relation(myId, [])
    yield relation.initGroupsList()

    # The updates that will be used to build reason strings
    convReasonUpdates = {}

    # Data that is sent to various plugins and returned by this function
    # XXX: myKey is depricated - use myId
    data = {"myId": myId, "orgId": orgId, "responses": responses,
            "likes": likes, "myLikes": myLikes, "items": items,
            "entities": entities, "tags": tags, "myKey": myId,
            "relations": relation}

    @defer.inlineCallbacks
    def fetchFeedItems(ids):
        rawFeedItems = yield db.get_slice(feedItemsId, "feedItems", ids) \
                                            if ids else defer.succeed([])
        for conv in rawFeedItems:
            convId = conv.super_column.name
            convUpdates = conv.super_column.columns
            responses[convId] = []
            likes[convId] = []
            latest = None

            updatesByType = {}
            for update in convUpdates:
                parts = update.value.split(':')
                updatesByType.setdefault(parts[0], []).append(parts)
                if parts[1] != myId:    # Ignore my own updates
                    latest = parts      # when displaying latest actors

            # Parse all notification to make sure we fetch any required
            # items, entities. and cache generic stuff that we display
            for tipe in updatesByType.keys():
                updates = updatesByType[tipe]

                if tipe in _feedUpdatePlugins:
                    (i,e) = _feedUpdatePlugins[tipe].parse(convId, updates)
                    toFetchItems.update(i)
                    toFetchEntities.update(e)

                if tipe == "L":
                    for update in updates:
                        if update[2] == convId:
                            likes[convId].append(update[1])
                        # XXX: Adding this item may break the sorting
                        #      of responses on this conversation
                        #      Bug #493
                        #else:
                        #    responses[convId].append(update[2])
                elif tipe in ["C", "Q"]:
                    for update in updates:
                        responses[convId].append(update[2])

            # Store any information that can be used to render
            # the reason strings when we have the required data
            if getReasons and latest:
                convReasonUpdates[convId] = updatesByType[latest[0]]

    # Fetch the feed if required and at the same time make sure
    # we delete unwanted items from the feed (cleanup).
    # NOTE: We assume that there will be very few deletes.
    nextPageStart = None
    if not convIds:
        feedId = feedId or myId
        allFetchedConvIds = set()   # Complete set of convIds fetched
        itemsFromFeed = {}          # All the key-values retrieved from feed
        keysFromFeed = []           # Sorted list of keys (used for paging)
        convIds = []                # List of convIds that will be displayed

        fetchStart = utils.decodeKey(start)
        fetchCount = count + 1

        while len(convIds) < count:
            fetchedConvIds = []

            # Use the getFn function if given.
            # NOTE: Part of this code is duplicated just below this.
            if getFn:
                results = yield getFn(start=fetchStart, count=fetchCount)
                for name, value in results.items():
                    keysFromFeed.append(name)
                    if value not in allFetchedConvIds:
                        fetchedConvIds.append(value)
                        allFetchedConvIds.add(value)
                        itemsFromFeed[name] = value
                    else:
                        deleteKeys.append(name)

            # Fetch user's feed when getFn isn't given.
            # NOTE: Part of this code is from above
            else:
                results = yield db.get_slice(feedId, feedSource,
                                             count=fetchCount,
                                             start=fetchStart, reverse=True)
                for col in results:
                    value = col.column.value
                    keysFromFeed.append(col.column.name)
                    if value not in allFetchedConvIds:
                        fetchedConvIds.append(value)
                        allFetchedConvIds.add(value)
                        itemsFromFeed[col.column.name] = value
                    else:
                        deleteKeys.append(col.column.name)

            # Initiate fetching feed items for all the conversation Ids.
            # Meanwhile we check if the authenticated user has access to
            # all the fetched conversation ids.
            # NOTE: Conversations would rarely be filtered out. So, we
            #       just go ahead with fetching data for all convs.
            feedItems_d.append(fetchFeedItems(fetchedConvIds))
            (filteredConvIds, deletedIds) = yield utils.fetchAndFilterConvs\
                                (fetchedConvIds, relation, items, myId, orgId)
            convIds.extend(filteredConvIds)
            deleted.extend(deletedIds)

            # Unless we are forced to fetch count number of items, we only
            # iterate till we fetch atleast half of them
            if (not forceCount and len(convIds) > (count/2)) or\
                    len(results) < fetchCount:
                break

            # If we need more items, we start fetching from where we
            # left in the previous iteration.
            fetchStart = keysFromFeed[-1]

        # If DB fetch got as many items as I requested
        # there may be additional items present in the feed
        # So, we cut one item from what we return and start the
        # next page from there.
        if len(results) == fetchCount:
            lastConvId = convIds[-1]
            for key in reversed(keysFromFeed):
                if key in itemsFromFeed and itemsFromFeed[key] == lastConvId:
                    nextPageStart = utils.encodeKey(key)
            convIds = convIds[:-1]

    else:
        (convIds, deletedIds) = yield utils.fetchAndFilterConvs(convIds,
                                            relation, items, myId, myOrgId)
        # NOTE: Unlike the above case where we fetch convIds from
        #       database (where we set the nextPageStart to a key),
        #       here we set nextPageStart to the convId.
        if len(convIds) > count:
            nextPageStart = utils.encodeKey(convIds[count])
            convIds = convIds[0:count]

        # Since convIds were directly passed to us, we would also
        # return the list of convIds deleted back to the caller.
        if deletedIds:
            data["deleted"] = deletedIds

    # We don't have any conversations to display!
    if not convIds:
        defer.returnValue({"conversations": []})

    # Delete any convs that were deleted from the feeds and
    # any duplicates that were marked for deletion
    cleanup_d = []
    if deleted:
        for key, value in itemsFromFeed.items():
            if value in deleted:
                deleteKeys.append(key)

        if cleanFn:
            d1 = cleanFn(list(deleteKeys))
        else:
            d1 = db.batch_remove({feedSource: [feedId]}, names=deleteKeys)

        d2 = db.batch_remove({'feedItems': [feedId]}, names=list(deleted))
        cleanup_d = [d1, d2]

    # We now have a filtered list of conversations that can be displayed
    # Let's wait till all the feed items have been fetched and processed
    yield defer.DeferredList(feedItems_d)

    # Fetch the remaining items (comments on the actual conversations)
    items_d = db.multiget_slice(toFetchItems, "items", ["meta" ,"attachments"])

    # Fetch tags on all the conversations that will be displayed
    for convId in convIds:
        conv = items[convId]
        toFetchEntities.add(conv["meta"]["owner"])
        if "target" in conv["meta"]:
            toFetchEntities.update(conv["meta"]["target"].split(','))
        toFetchTags.update(conv.get("tags",{}).keys())

    tags_d = db.get_slice(orgId, "orgTags", toFetchTags) \
                                if toFetchTags else defer.succeed([])

    # Fetch the list of my likes.
    # XXX: Latency can be pretty high here becuase many nodes will have to
    #      be contacted for the information.  Alternative could be to cache
    #      all likes by a user somewhere.
    myLikes_d = db.multiget(toFetchItems.union(convIds), "itemLikes", myId)

    # Fetch extra data that is required to render special items
    # We already fetched the conversation items, plugins merely
    # add more data to the already fetched items
    for convId in convIds[:]:
        itemType = items[convId]["meta"]["type"]
        if itemType in plugins:
            try:
                entityIds = yield plugins[itemType].fetchData(data, convId)
                toFetchEntities.update(entityIds)
            except Exception, e:
                log.err(e)
                convIds.remove(convId)

    # Fetch all required entities
    entities_d = db.multiget_slice(toFetchEntities, "entities", ["basic"])

    # Results of previously initiated fetches (items, tags, entities, likes)
    fetchedItems = yield items_d
    items.update(utils.multiSuperColumnsToDict(fetchedItems))

    fetchedTags = yield tags_d
    tags.update(utils.supercolumnsToDict(fetchedTags))

    fetchedMyLikes = yield myLikes_d
    myLikes.update(utils.multiColumnsToDict(fetchedMyLikes))

    fetchedEntities = yield entities_d
    entities.update(utils.multiSuperColumnsToDict(fetchedEntities))

    # Time to build reason strings (and reason userIds)
    if getReasons:
        reasonStr = {}
        reasonUserIds = {}
        for convId in convReasonUpdates.keys():
            updates = convReasonUpdates.get(convId, [])
            tipe = updates[-1][0]
            if tipe in _feedUpdatePlugins:
                rstr, ruid = _feedUpdatePlugins[tipe]\
                                .reason(convId, updates, data)
                reasonStr[convId] = rstr
                reasonUserIds[convId] = ruid
        data.update({'reasonStr': reasonStr, 'reasonUserIds':reasonUserIds})

    # Wait till the deletions get through :)
    yield defer.DeferredList(cleanup_d)

    data.update({'nextPageStart': nextPageStart, 'conversations': convIds})
    defer.returnValue(data)


