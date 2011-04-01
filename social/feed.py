
import time
import uuid

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base, plugins, _, __
from social.template    import render, renderDef, renderScriptBlock
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE


@defer.inlineCallbacks
def deleteFromFeed(userKey, itemKey, parentKey,
                   itemType, itemOwner, responseType):
    # fix: itemOwner is either the person who owns the item
    #       or person who liked the item. RENAME the variable.
    cols = yield Db.get_slice(userKey, "feedItems",
                              super_column=parentKey, reverse=True)
    cols = utils.columnsToDict(cols)

    for tuuid, val in cols.items():
        rtype, poster, key =  val.split(":")[0:3]
        if rtype == responseType and poster == itemOwner and key == itemKey:
            yield Db.remove(userKey, "feedItems", tuuid, parentKey)
            yield Db.remove(userKey, "feed", tuuid)
            if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                yield Db.remove(userKey, "feed_"+itemType, tuuid)

            break


@defer.inlineCallbacks
def deleteFromOthersFeed(userKey, itemKey,parentKey, itemType,
                         acl, convOwner, responseType):
    others = yield utils.expandAcl(userKey, acl, convOwner)
    for key in others:
        yield deleteFromFeed(key, itemKey, parentKey,
                             itemType, userKey, responseType )


@defer.inlineCallbacks
def pushToOthersFeed(userKey, timeuuid, itemKey,parentKey,
                    acl, responseType, itemType, convOwner):
    others = yield utils.expandAcl(userKey, acl, convOwner)
    for key in others:
        yield pushToFeed(key, timeuuid, itemKey, parentKey,
                         responseType, itemType, convOwner, userKey)


@defer.inlineCallbacks
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
                itemType, convOwner=None, commentOwner=None):
    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner

    yield Db.insert(userKey, "feed", parentKey, timeuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield Db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)

    yield updateFeedResponses(userKey, parentKey, itemKey, timeuuid,
                               itemType, responseType, convOwner, commentOwner)


@defer.inlineCallbacks
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid,
                        itemType, responseType, convOwner, commentOwner):

    feedItemValue = ":".join([responseType, commentOwner, itemKey, ''])
    tmp, oldest = {}, None

    cols = yield Db.get_slice(userKey, "feedItems",
                              super_column = parentKey, reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)

    for tuuid, val in cols.items():
        rtype = val.split(':')[0]
        if rtype not in  ('!', 'I'):
            tmp.setdefault(val.split(':')[0], []).append(tuuid)
            oldest = tuuid

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


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

    # TODO: ACLs
    @defer.inlineCallbacks
    def _getFeedItems(self, request, itemIds=None, start='', count=10, entityId=None):
        toFetchItems = set()    # Items and entities that need to be fetched
        toFetchEntities = set() #
        toFetchTags = set()
        args = {}

        authinfo = request.getSession(IAuthInfo)
        userKey = authinfo.username
        myOrgId = authinfo.organization

        # Fetch entity(org/group) feed if entityId is given
        key = entityId if entityId else userKey

        # 1. Fetch the list of root items (conversations) that will be shown
        convs = []
        nextPageStart = None
        if itemIds:
            convs.extend(itemIds)
            toFetchItems.update(set(itemIds))
        else:
            keysFromFeed = []
            fetchStart = utils.decodeKey(start)
            fetchCount = count + 5
            while len(convs) < count:
                cols = yield Db.get_slice(key, "feed", count=fetchCount,
                                          start=fetchStart, reverse=True)
                for col in cols:
                    value = col.column.value
                    if value not in toFetchItems:
                        convs.append(value)
                        toFetchItems.add(value)
                        keysFromFeed.append(col.column.name)

                if len(cols) < fetchCount:
                    break
                fetchStart = cols[-1].column.name

            if len(keysFromFeed) > count:
                nextPageStart = utils.encodeKey(keysFromFeed[count])
                convs = convs[0:count]

        if not convs:
            defer.returnValue({"conversations": convs})

        # 2. Fetch list of notifications that we have for above conversations
        #    and check if we have enough responses to be shown in the feed.
        #    If not fetch responses for those conversations.
        rawFeedItems = yield Db.get_slice(key, "feedItems", convs)
        reasonUserIds = {}
        reasonTmpl = {}
        likes = {}
        responses = {}
        toFetchResponses = set()
        for conversation in rawFeedItems:
            convId = conversation.super_column.name
            mostRecentItem = None
            columns = conversation.super_column.columns
            likes[convId] = []
            responses[convId] = []
            responseUsers = []
            rootItem = None

            # Collect information about recent updates by my friends
            # and subscriptions on this item.
            for update in columns:
                # X:<user>:<item>:<entities>
                item = update.value.split(':')

                toFetchEntities.add(item[1])
                if len(item) > 3 and len(item[3]):
                    toFetchEntities.update(item[3].split(","))

                type = item[0]
                if type == "C":
                    responseUsers.append(item[1])
                    responses[convId].append(item[2])
                    mostRecentItem = item
                    toFetchItems.add(item[2])
                elif type == "L" and convId == item[2]:
                    likes[convId].append(item[1])
                    mostRecentItem = item
                elif type == "L":
                    mostRecentItem = item
                    toFetchItems.add(item[2])
                elif type == "I" or type == "!":
                    rootItem = item[1:3]
                    if type == "I":
                        mostRecentItem = item

            # Build a template used to show the reason for having this item
            # as part of the user feed.
            if mostRecentItem:
                (type, userId, itemId) = mostRecentItem[0:3]
                if type == "C":
                    reasonUserIds[convId] = set(responseUsers)
                    reasonTmpl[convId] = ["%s commented on %s's %s",
                                          "%s and %s commented on %s's %s",
                                          "%s, %s and %s commented on %s's %s"]\
                                         [len(reasonUserIds[convId])-1]
                elif type == "L" and itemId == convId:
                    reasonUserIds[convId] = set(likes[convId])
                    reasonTmpl[convId] = ["%s liked %s's %s",
                                          "%s and %s liked %s's %s",
                                          "%s, %s and %s liked %s's %s"]\
                                         [len(reasonUserIds[convId])-1]
                elif type == "L":
                    reasonUserIds[convId] = set([userId])
                    reasonTmpl[convId] = "%s liked a comment on %s's %s"

                # Check if we have to fetch more responses for this conversation
                if len(responses[convId]) < 2:
                    toFetchResponses.add(convId)

        # 2.1 Fetch more responses, if required
        itemResponses = yield Db.multiget_slice(toFetchResponses,
                                                "itemResponses",
                                                reverse=True, count=2)
        for convId, comments in itemResponses.items():
            for comment in comments:
                userKey_, itemKey = comment.column.value.split(':')
                if itemKey not in toFetchItems and len(responses[convId]) < 2:
                    responses[convId].append(itemKey)
                    toFetchItems.add(itemKey)
                    toFetchEntities.add(userKey_)

        # Concurrently fetch items and entities
        fetchedItems = yield Db.multiget_slice(toFetchItems, "items",
                                               ["meta", "tags"])
        items = utils.multiSuperColumnsToDict(fetchedItems)
        args["items"] = items
        extraDataDeferreds = []

        for convId in convs:
            meta = items[convId]["meta"]
            itemType = meta["type"]
            toFetchEntities.add(meta["owner"])
            if "target" in meta:
                toFetchEntities.add(meta["target"])

            toFetchTags.update(items[convId].get("tags", {}).keys())

            if itemType in plugins:
                d =  plugins[itemType].fetchData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchEntities.update(ret)

        d1 = Db.multiget_slice(toFetchEntities, "entities", ["basic"])
        d2 = Db.multiget(toFetchItems, "itemLikes", userKey)
        d3 = Db.get_slice(myOrgId, "orgTags", toFetchTags) \
                                if toFetchTags else defer.succeed([])

        fetchedEntities = yield d1
        fetchedMyLikes = yield d2
        fetchedTags = yield d3

        entities = utils.multiSuperColumnsToDict(fetchedEntities)
        myLikes = utils.multiColumnsToDict(fetchedMyLikes)
        args["tags"] = utils.supercolumnsToDict(fetchedTags)

        # We got all our data, do the remaining processing before
        # rendering the template.
        reasonStr = {}
        likeStr = {}
        for convId in convs:
            template = reasonTmpl.get(convId, None)
            conv = items[convId]
            ownerId = conv["meta"]["owner"]

            # Build reason string
            if template:
                vals = [utils.userName(id, entities[id], "conv-user-cause")\
                        for id in reasonUserIds[convId]]
                vals.append(utils.userName(ownerId, entities[ownerId]))
                itemType = conv["meta"]["type"]
                vals.append(utils.itemLink(convId, itemType))
                reasonStr[convId] = _(template) % tuple(vals)

            # Build like string
            likesCount = int(conv["meta"].get("likesCount", "0"))
            userIds = [x for x in likes[convId]]
            if userKey in userIds:
                userIds.remove(userKey)

            userIds = userIds[-2:]
            template = None
            if len(myLikes[convId]):
                likesCount -= (1 + len(userIds))
                if likesCount <= 0:
                    template = ["You like this",
                                "You and %s like this",
                                "You, %s and %s like this"][len(userIds)]
                elif likesCount == 1:
                    template = ["You and 1 other person like this",
                        "You, %s and 1 other person like this",
                        "You, %s, %s and 1 other person like this"][len(userIds)]
                else:
                    template = ["You and %s other people like this",
                        "You, %s and %s other people like this",
                        "You, %s, %s and %s other people like this"][len(userIds)]
            else:
                likesCount -= len(userIds)
                if likesCount == 0 and len(userIds) > 0:
                    template = ["%s likes this",
                                "%s and %s like this"][len(userIds)-1]
                if likesCount == 1:
                    template = ["1 person likes this",
                        "%s and 1 other person like this",
                        "%s, %s and 1 other people like this"][len(userIds)]
                elif likesCount > 1:
                    template = ["%s people like this",
                        "%s and %s other people like this",
                        "%s, %s and %s other people like this"][len(userIds)]

            if template:
                vals = [utils.userName(id, entities[id]) for id in userIds]
                if likesCount > 1:
                    vals.append(str(likesCount))

                likeStr[convId] = _(template) % tuple(vals)

        data = {"entities": entities, "responses": responses,
                "myLikes": myLikes, "reasonStr": reasonStr,
                "likeStr": likeStr, "conversations": convs,
                "nextPageStart": nextPageStart}
        args.update(data)
        defer.returnValue(args)


    @defer.inlineCallbacks
    def _render(self, request, entityId=None):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        if entityId:
            entity = yield Db.get_slice(entityId, "entities", ["basic"])
            entity = utils.supercolumnsToDict(entity)
            entityType = entity["basic"]['type']
            if entityType == "org":
                if entityId != myOrgId:
                    errors.InvalidRequest()
                args["heading"] = "Company Feed"
            elif entityType == "group":
                # XXX: Check if I am a member of this group!
                args["heading"] = "Group Feed"
            else:
                errors.InvalidRequest()

        if script and landing:
            yield render(request, "feed.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)

        if script and not fromFetchMore:
            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing, "#share-block", "set", **args)
            yield self._renderShareBlock(request, "status")

        if entityId:
            feedItems = yield self._getFeedItems(request, start=start, entityId=entityId)
        else:
            feedItems = yield self._getFeedItems(request, start=start)

        args.update(feedItems)
        if script:
            if fromFetchMore:
                yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                        "#next-load-wrapper", "replace", **args)
            else:
                yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                        "#user-feed", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)


    @defer.inlineCallbacks
    def _renderShareBlock(self, request, typ):
        landing = not self._ajax
        templateFile = "feed.mako"
        renderDef = "share_status"

        plugin = plugins.get(typ, None)
        if plugin:
            templateFile, renderDef = plugin.shareBlockProvider()

        yield renderScriptBlock(request, templateFile, renderDef,
                                landing, "#sharebar", "set", True,
                                handlers={"onload": "$('#sharebar-links .selected').removeClass('selected'); $('#sharebar-link-%s').addClass('selected');" % (typ)})


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            entityId = utils.getRequestArg(request, "id")
            d = self._render(request, entityId)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])

        return self._epilogue(request, d)
