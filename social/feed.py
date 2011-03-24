
import time
import uuid

from ordereddict        import OrderedDict
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from telephus.cassandra import ttypes

from social             import Db, utils, base, plugins, _, __
from social.template    import render, renderDef, renderScriptBlock
from social.isocial     import IAuthInfo
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
    def _getFeedItems(self, userKey, itemKey=None, count=10,
                      orgKey=None, groupId=None):
        toFetchItems = set()    # Items, users and groups that need to be fetched
        toFetchUsers = set()    #
        toFetchGroups = set()   #
        args = {}
        args["myKey"] = userKey
        #fetch company feed if orgKey is given
        key = groupId if groupId else (orgKey if orgKey else userKey)

        # 1. Fetch the list of root items (conversations) that will be shown
        convs = []
        if itemKey:
            convs.append(itemKey)
            toFetchItems.add(itemKey)
        else:
            start = ""
            fetchCount = count + 5
            while len(convs) < count:
                cols = yield Db.get_slice(key, "feed", count=fetchCount,
                                          start=start, reverse=True)
                for col in cols:
                    value = col.column.value
                    if value not in toFetchItems:
                        convs.append(value)
                        toFetchItems.add(value)
                if len(cols) < fetchCount:
                    break
                start = cols[-1].column.name

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
                # X:<user>:<item>:<users>:<groups>
                item = update.value.split(':')

                toFetchUsers.add(item[1])
                if len(item) > 3 and len(item[3]):
                    toFetchUsers.update(item[3].split(","))
                if len(item) > 4 and len(item[4]):
                    toFetchGroups.update(item[4].split(","))

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
                    toFetchUsers.add(userKey_)

        # Concurrently fetch items, users and groups
        # TODO: fecthing options to display polls. plugin should handle it
        fetchedItems = yield Db.multiget_slice(toFetchItems, "items",
                                                ["meta", "options"])
        items = utils.multiSuperColumnsToDict(fetchedItems)
        args["items"] = items
        extraDataDeferreds = []

        for convId in convs:
            itemType = items[convId]["meta"]["type"]
            if itemType in plugins:
                d =  plugins[itemType].fetchData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchUsers_, toFetchGroups_ = ret
                toFetchUsers.update(toFetchUsers_)
                toFetchGroups.update(toFetchGroups_)

        d2 = Db.multiget_slice(toFetchUsers, "entities", ["basic"])
        d3 = Db.multiget_slice(toFetchGroups, "entities", ["basic"])
        d4 = Db.multiget(toFetchItems, "itemLikes", userKey)
        fetchedUsers = yield d2
        fetchedGroups = yield d3
        fetchedMyLikes = yield d4

        users = utils.multiSuperColumnsToDict(fetchedUsers)
        groups = utils.multiSuperColumnsToDict(fetchedGroups)
        myLikes = utils.multiColumnsToDict(fetchedMyLikes)

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
                vals = [utils.userName(id, users[id], "conv-user-cause")\
                        for id in reasonUserIds[convId]]
                vals.append(utils.userName(ownerId, users[ownerId]))
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
                vals = [utils.userName(id, users[id]) for id in userIds]
                if likesCount > 1:
                    vals.append(str(likesCount))

                likeStr[convId] = _(template) % tuple(vals)

        data = {"users": users, "groups": groups,
                "responses": responses, "myLikes": myLikes,
                "reasonStr": reasonStr, "likeStr": likeStr,
                "conversations": convs}
        args.update(data)
        defer.returnValue(args)


    @defer.inlineCallbacks
    def _render(self, request, orgFeed=False, groupFeed=False):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        myOrg = args["orgKey"]
        args["heading"] = "Company Feed" if orgFeed else \
                                    ("Group Feed" if groupFeed else "News Feed")

        if orgFeed:
            orgKey = yield utils.getValidEntityId(request, "id", "org")
            if not orgKey or orgKey != myOrg:
                errors.InvalidRequest()

        if groupFeed:
            groupId = yield utils.getValidEntityId(request, "id", "group")

        if script and landing:
            yield render(request, "feed.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing, "#share-block", "set", **args)
            yield self._renderShareBlock(request, "status")
        if orgFeed:
            feedItems = yield self._getFeedItems(myKey, orgKey=orgKey)
        elif groupFeed:
            feedItems = yield self._getFeedItems(myKey, groupId = groupId)

        else:
            feedItems = yield self._getFeedItems(myKey)
        args.update(feedItems)
        if script:
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

        if segmentCount == 0 :
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == "org":
            d = self._render(request, orgFeed=True)
        elif segmentCount == 1 and request.postpath[0] == "group":
            d = self._render(request, groupFeed=True)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])

        return self._epilogue(request, d)
