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
                     others=None, tagId=''):
    if not others:
        others = yield utils.expandAcl(userKey, acl, convOwner)
    for key in others:
        yield pushToFeed(key, timeuuid, itemKey, parentKey,
                         responseType, itemType, convOwner,
                         userKey, tagId)


@profile
@defer.inlineCallbacks
@dump_args
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
                itemType, convOwner=None, commentOwner=None, tagId=''):
    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner

    yield Db.insert(userKey, "feed", parentKey, timeuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield Db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)

    yield updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                               responseType, convOwner, commentOwner, tagId)


@profile
@defer.inlineCallbacks
@dump_args
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                        responseType, convOwner, commentOwner, tagId=''):

    feedItemValue = ":".join([responseType, commentOwner, itemKey,'', tagId])
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


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

    # TODO: ACLs

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _getFeedItems(self, request, itemIds=None, start='', count=10, entityId=None):
        toFetchItems = set()    # Items and entities that need to be fetched
        toFetchEntities = set() #
        toFetchTags = set()
        args = {}

        authinfo = request.getSession(IAuthInfo)
        userKey = authinfo.username
        myOrgId = authinfo.organization

        args["myKey"] = userKey
        relation = Relation(userKey, [])
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initSubscriptionsList(),
                                  relation.initPendingList(),
                                  relation.initFollowersList()])

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

            if len(keysFromFeed) > count:   # We have more items than count
                nextPageStart = utils.encodeKey(keysFromFeed[count])
                convs = convs[0:count]
            elif len(cols) == fetchCount:   # We got duplicate items in feed
                nextPageStart = utils.encodeKey(keysFromFeed[-1])
                convs = convs[0:-1]

        if not convs:
            defer.returnValue({"conversations": convs})

        # 2. Fetch list of notifications that we have for above conversations
        #    and check if we have enough responses to be shown in the feed.
        #    If not fetch responses for those conversations.
        rawFeedItems = yield Db.get_slice(key, "feedItems", convs)
        reasonUserIds = {}
        reasonTagId = {}
        reasonTmpl = {}
        likes = {}
        responses = {}
        for conversation in rawFeedItems:
            convId = conversation.super_column.name
            mostRecentItem = None
            columns = conversation.super_column.columns
            likes[convId] = []
            responses[convId] = []
            responseUsers = []

            tagId = None
            rootItem = None

            # Collect information about recent updates by my friends
            # and subscriptions on this item.
            for update in columns:
                # X:<user>:<item>:<entities>:<tag>
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
                elif type == "T":
                    mostRecentItem = item
                    if len(item) >4 and len(item[4]):
                        tagId = item[4]
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
                elif type == "T":
                    reasonUserIds[convId] = set([userId])
                    reasonTagId[convId] = tagId
                    reasonTmpl[convId] = "%s applied %s tag on %s's %s"

        # Concurrently fetch items and entities
        fetchedItems = yield Db.multiget_slice(toFetchItems, "items",
                                               ["meta", "tags"])
        items = utils.multiSuperColumnsToDict(fetchedItems)
        args["items"] = items
        extraDataDeferreds = []
        userGroups = yield Db.get_slice(userKey, "userGroups")
        userGroups = utils.columnsToDict(userGroups)

        # fetch extra data (polls/events/links)
        for convId in convs[:]:
            meta = items[convId]["meta"]
            owner = meta["owner"]

            if not utils.checkAcl(userKey, meta["acl"], owner, relation,
                                  myOrgId, userGroups.keys()):
                convs.remove(convId)
                # delete the items from feed
                continue

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
        fetchedTags = utils.supercolumnsToDict(fetchedTags)
        args["tags"] = fetchedTags

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
                if reasonTagId.get(convId, None):
                    tagId = reasonTagId[convId]
                    tagname = fetchedTags[tagId]["title"]
                    vals.append("<a class='ajax' href='/tags?id=%s'>%s</a>" %(tagId, tagname))
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


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request, entityId=None):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        if entityId:
            entity = yield Db.get_slice(entityId, "entities", ["basic", "admins"])
            entity = utils.supercolumnsToDict(entity)
            entityType = entity["basic"]['type']
            if entityType == "org":
                if entityId != myOrgId:
                    errors.InvalidRequest()
                args["feedTitle"] = _("Company Feed: %s") % entity["basic"]["name"]
            elif entityType == "group":
                args["feedTitle"] = _("Group Feed: %s") % entity["basic"]["name"]
                args["groupAdmins"] = entity["admins"]
                args["groupId"] = entityId
            else:
                errors.InvalidRequest()
        else:
            args["feedTitle"] = _("News Feed")

        if script and landing:
            yield render(request, "feed.mako", **args)
        elif script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        elif script and "feedTitle" in args:
            yield renderScriptBlock(request, "feed.mako", "feed_title",
                                    landing, "#title", "set", **args)

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
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            if fromFetchMore:
                yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                        "#next-load-wrapper", "replace", True,
                                        handlers={"onload": onload}, **args)
            else:
                yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                        "#user-feed", "set", True,
                                        handlers={"onload": onload}, **args)
            yield renderScriptBlock(request, "feed.mako", "groupLinks",
                                    landing, "#group-links", "set",  **args)


        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)


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
            entityId = utils.getRequestArg(request, "id")
            d = self._render(request, entityId)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])

        return self._epilogue(request, d)
