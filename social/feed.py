import time
import uuid

from twisted.internet   import defer
from twisted.web        import server
from twisted.plugin     import getPlugins

from social             import db, utils, base, plugins, _, __, errors, people
from social             import template as t
from social.isocial     import IAuthInfo, IFeedUpdateType
from social.relations   import Relation
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE
from social.constants   import SUGGESTION_PER_PAGE
from social.logging     import profile, dump_args, log

@defer.inlineCallbacks
def deleteUserFeed(userId, itemType, tuuid):
    yield db.remove(userId, "userItems", tuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield db.remove(userId, "userItems_"+itemType, tuuid)


@defer.inlineCallbacks
def deleteFeed(userId, orgId, itemId, convId, itemType, acl, convOwner,
               responseType, others=None, tagId='', deleteAll=False):
    #
    # Wrapper around deleteFromFeed and deleteFromOthersFeed
    #
    yield deleteFromFeed(userId, itemId, convId, itemType,
                         userId, responseType, tagId )
    if deleteAll:
        yield deleteFromOthersFeed(userId, orgId, itemId, convId, itemType, acl,
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
def deleteFromOthersFeed(userId, orgId, itemId, convId, itemType, acl,
                         convOwner, responseType, others=None, tagId=''):
    if not others:
        others = yield utils.expandAcl(userId, orgId, acl, convId, convOwner)

    for key in others:
        yield deleteFromFeed(key, itemId, convId, itemType,
                             userId, responseType, tagId=tagId)


@profile
@defer.inlineCallbacks
@dump_args
def pushToOthersFeed(userKey, orgId, timeuuid, itemKey, parentKey, acl,
                     responseType, itemType, convOwner, others=None,
                     tagId='', entities=None, promoteActor=True):
    if not others:
        others = yield utils.expandAcl(userKey, orgId, acl, parentKey, convOwner)

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


class Feed(object):
    plugins =  dict()
    for plg in getPlugins(IFeedUpdateType):
        if not hasattr(plg, "disabled") or not plg.disabled:
            plugins[plg.updateType] = plg

    @classmethod
    @defer.inlineCallbacks
    def get(cls, auth, feedId=None, feedItemsId=None, convIds=None,
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

                    if tipe in cls.plugins:
                        (i,e) = cls.plugins[tipe].parse(convId, updates)
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
                if tipe in cls.plugins:
                    rstr, ruid = cls.plugins[tipe]\
                                    .reason(convId, updates, data)
                    reasonStr[convId] = rstr
                    reasonUserIds[convId] = ruid
            data.update({'reasonStr': reasonStr, 'reasonUserIds':reasonUserIds})

        # Wait till the deletions get through :)
        yield defer.DeferredList(cleanup_d)

        data.update({'nextPageStart': nextPageStart, 'conversations': convIds})
        defer.returnValue(data)


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}
    _templates = ['feed.mako']

    def paths(self):
        return  [('GET', '^/ui/share/(?P<typ>[^/]+)$', self.renderShareBlock),
                 ('GET', '^/(?P<entityId>[^/]*)$',     self.get)]

    def get(self, request, entityId=None):
        itemType = utils.getRequestArg(request, 'type')
        start = utils.getRequestArg(request, 'start') or ''
        more = utils.getRequestArg(request, 'more') or False

        if more:
            return self._renderMore(request, entityId, start, itemType)
        else:
            return self._render(request, entityId, start, itemType)

    def renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            plugin.renderShareBlock(request, self._ajax)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request, entityId, start, itemType):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        itemType = utils.getRequestArg(request, 'type')
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
                request.redirect("/group?id=%s"%(entityId))
                defer.returnValue(None)
            else:
                if entityId != myId:
                    raise errors.EntityAccessDenied("user", entityId)

        feedId = entityId or myId
        args["feedTitle"] = feedTitle
        args["menuId"] = menuId
        args["feedId"] = feedId

        if script and landing:
            t.render(request, "feed.mako", **args)
            request.write('<script>$("#invite-form").html5form({messages: "en"})</script>')
        elif script and appchange:
            onload = '$("#invite-form").html5form({messages: "en"})'
            t.renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", handlers={'onload':onload}, **args)
        elif script and feedTitle:
            t.renderScriptBlock(request, "feed.mako", "feed_title",
                                landing, "#title", "set", True,
                                handlers={"onload": "$$.menu.selectItem('%s')"%(menuId)}, **args)

        if script:
            handlers = {}
            handlers["onload"] = handlers.get("onload", "") +\
                                 "$$.files.init('sharebar-attach');"
            t.renderScriptBlock(request, "feed.mako", "share_block",
                                landing, "#share-block", "set",
                                handlers=handlers, **args)
            yield self.renderShareBlock(request, "status")

        feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                   feedId=feedId, start=start,
                                   itemType=itemType)
        args.update(feedItems)
        args['itemType'] = itemType

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
            onload = """
                        (function(obj){$$.convs.load(obj);})(this);
                        $('#feed-side-block-container').empty();
                     """
            t.renderScriptBlock(request, "feed.mako", "feed", landing,
                                "#user-feed", "set", True,
                                handlers={"onload": onload}, **args)
            t.renderScriptBlock(request, "feed.mako", "_suggestions",
                                landing, "#suggestions", "set", True, **args)

            for pluginType in plugins:
                plugin = plugins[pluginType]
                if hasattr(plugin, 'renderFeedSideBlock'):
                    if not entityId: entityId = myId
                    yield plugin.renderFeedSideBlock(request, landing,
                                                                 entityId, args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            t.render(request, "feed.mako", **args)

    # The client has scripts and this is an ajax request
    @defer.inlineCallbacks
    def _renderMore(self, request, entityId, start, itemType):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        entity = yield db.get_slice(entityId, "entities", ["basic"])
        entity = utils.supercolumnsToDict(entity)
        if entity and entity["basic"].get("type", '') == "group":
            errors.InvalidRequest("group feed will not be fetched.")

        feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                   feedId=entityId, start=start,
                                   itemType=itemType)
        args.update(feedItems)
        args["feedId"] = entityId
        args['itemType'] = itemType

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        t.renderScriptBlock(request, "feed.mako", "feed", False,
                            "#next-load-wrapper", "replace", True,
                            handlers={"onload": onload}, **args)

    @defer.inlineCallbacks
    def _renderChooseAudience(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        onload = "$('form').html5form({messages: 'en'});"
        t.renderScriptBlock(request, "feed.mako", "customAudience", False,
                            "#custom-audience-dlg", "set", True,
                            handlers={"onload": onload}, **args)

