
import time
import uuid

from ordereddict        import OrderedDict
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from telephus.cassandra import ttypes

from social             import Db, utils, base
from social.template    import render, renderDef, renderScriptBlock
from social.auth        import IAuthInfo
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE


@defer.inlineCallbacks
def deleteFromFeed(userKey, itemKey, parentKey, itemType):
    cols = yield Db.get_slice(userKey,
                              "feedItems",
                              super_column=parentKey,
                              reverse=True)
    cols = utils.columnsToDict(cols)
    for tuuid, val in cols.items():
        if val.split(':')[2] == itemKey:
            yield Db.remove(userKey, "feedItems", tuuid, parentKey)
            yield Db.remove(userKey, "feed", tuuid)
            yield Db.remove(userKey, "feed_"+itemType, tuuid)
            break

@defer.inlineCallbacks
def deleteFromOthersFeed(userKey, itemKey,
                         parentKey, itemType,
                         acl, parentUserKey):

    others = yield utils.expandAcl(userKey, acl, parentUserKey)
    for key in others:
        yield deleteFromFeed(key, itemKey, parentKey, itemType)

@defer.inlineCallbacks
def pushToOthersFeed(userKey, timeuuid, itemKey,
                     parentKey, acl, responseType,
                     itemType, parentUserKey):

    others = yield utils.expandAcl(userKey, acl, parentUserKey)
    for key in others:
        yield pushToFeed(key, timeuuid,itemKey, parentKey,
                         responseType, itemType, parentUserKey, userKey)

@defer.inlineCallbacks
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
                itemType, convOwner=None, commentOwner=None):

    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner
    yield Db.insert(userKey, "feed", parentKey, timeuuid)
    yield Db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)
    yield  updateFeedResponses(userKey, parentKey, itemKey, timeuuid,
                               itemType, responseType, convOwner, commentOwner)


@defer.inlineCallbacks
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid,
                        itemType, responseType, convOwner, commentOwner):

    feedItemValue = ":".join([responseType, commentOwner, itemKey, ''])
    tmp, oldest = {}, None

    cols = yield Db.get_slice(userKey,
                              "feedItems",
                              super_column = parentKey,
                              reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)

    for tuuid, val in cols.items():
        rtype = val.split(':')[0]
        if rtype != '!':
            tmp.setdefault(val.split(':')[0], []).append(tuuid)
            oldest = tuuid

    totalItems = len(cols)
    noOfItems = len(tmp.get(responseType, []))

    if noOfItems == MAXFEEDITEMSBYTYPE:
        oldest = tmp[responseType][noOfItems-1]

    if noOfItems == MAXFEEDITEMSBYTYPE or totalItems == MAXFEEDITEMS:
        yield Db.remove(userKey, "feedItems", oldest, parentKey)
        yield Db.remove(userKey, "feed", oldest)
        yield Db.remove(userKey, "feed_"+itemType, oldest)

    if totalItems == 0 and responseType != 'I':
        value = ":".join(["!", convOwner, parentKey, ""])
        tuuid = uuid.uuid1().bytes
        yield Db.batch_insert(userKey, "feedItems", {parentKey:{tuuid:value}})

    yield Db.batch_insert(userKey, "feedItems", {parentKey:{timeuuid: feedItemValue}})


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @defer.inlineCallbacks
    def getItems(self, userKey, itemKey=None, count=10):
        toFetchItems = set()    # Items, users and groups that need to be fetched
        toFetchUsers = set()    #
        toFetchGroups = set()   #

        # 1. Fetch the list of root items (conversations) that will be shown
        items = OrderedDict()
        if itemKey:
            items[itemKey] = [itemKey]
            toFetchItems.add(itemKey)
        else:
            cols = yield Db.get_slice(userKey, "feed", count=count, reverse=True)
            for col in cols:
                value = col.column.value
                items[value] = [value]
                toFetchItems.add(value)

        # 2. Fetch list of notifications that we have for above conversations and
        #    check if we have enough responses to be shown in the feed. If not
        #    fetch responses for those conversations.
        rawFeedItems = yield Db.get_slice(userKey, "feedItems", items)
        feedItems = dict()
        toFetchResponses = set()
        for conversation in rawFeedItems:
            convId = conversation.super_column.name
            feedItems[convId] = []
            numResponses = 0
            for update in conversation.super_column.columns:
                # X:<user>:<item>:<users>:<groups>
                item = update.value.split(':')
                feedItems[convId].append(item[0:3])

                toFetchUsers.add(item[1])
                if len(item) > 3 and len(item[3]):
                    toFetchUsers.update(item[3].split(","))
                if len(item) > 4 and len(item[4]):
                    toFetchGroups.update(item[4].split(","))

                if item[0] == "C":
                    items[convId].append(item[2])
                    toFetchItems.add(item[2])
                    numResponses += 1

            if numResponses < 2:
                toFetchResponses.add(convId)

        # 2.1 Fetch more responses, if required
        itemResponses = yield Db.multiget_slice(toFetchResponses, "itemResponses",
                                                reverse=True, count=2)
        for convId, responses in itemResponses.items():
            for response in responses:
                userKey, itemKey = response.column.value.split(':')
                if len(items[convId]) < 2:
                    items[convId].append(itemKey)
                    toFetchItems.add(itemKey)
                    toFetchUsers.add(userKey)

        # Finally, concurrently fetch items, users and groups
        d1 = Db.multiget_slice(toFetchItems, "items", ["data", "meta"])
        d2 = Db.multiget_slice(toFetchUsers, "users", ["basic"])
        d3 = Db.multiget_slice(toFetchGroups, "groups", ["basic"])
        itemData = yield d1
        userData = yield d2
        groupData = yield d3

        defer.returnValue([items, feedItems,
                           utils.multiSuperColumnsToDict(itemData),
                           utils.multiSuperColumnsToDict(userData),
                           utils.multiSuperColumnsToDict(groupData)])

    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args) = self._getBasicArgs(request)

        myKey = args["myKey"]
        col = yield Db.get_slice(myKey, "users")
        me = utils.supercolumnsToDict(col)

        args["me"] = me
        landing = not self._ajax

        if script and landing:
            yield render(request, "feed.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing, "#share-block", "set", **args)
            yield self._renderShareBlock(request, "status")

        items, feed, itemData, userData, groupData = yield self.getItems(myKey)
        args["conversations"] = items
        args["feedItems"] = feed
        args["items"] = itemData
        args["users"] = userData
        args["groups"] = groupData

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
        renderDef = "share_status"

        if typ == "link":
            renderDef = "share_link"
        elif typ == "document":
            renderDef = "share_document"

        yield renderScriptBlock(request, "feed.mako", renderDef,
                                landing, "#sharebar", "set", True,
                                handlers={"onload": "$('#sharebar-links .selected').removeClass('selected'); $('#sharebar-link-%s').addClass('selected'); $('#share-form').attr('action', '/feed/share/%s');" % (typ, typ)})

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 2 and request.postpath[0] == "share":
            if self._ajax:
                d = self._renderShareBlock(request, request.postpath[1])
        elif segmentCount ==1 and request.postpath[0] == "like":
            if self._ajax:
                d = self._setLike(request)

        elif segmentCount ==1 and request.postpath[0] == 'unlike':
            if self._ajax:
                d = self._setUnlike(request)

        if d:
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            def callback(response):
                request.finish()
            d.addCallbacks(callback, errback)
        else:
            request.finish()

        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _setLike(self, request):
        itemKey = utils.getRequestArg(request, "itemKey")
        parent =  utils.getRequestArg(request, "parent")
        parentUserKey = utils.getRequestArg(request, "parentUserId")
        userKey = request.getSession(IAuthInfo).username
        typ = utils.getRequestArg(request, "type")
        acl = utils.getRequestArg(request, "acl")
        if not (typ and acl and parentUserKey):
            cols = yield Db.get_slice(parent, "items",
                                        ["type", "acl", "owner"],
                                        super_column = "meta")
            cols = utils.columnsToDict(cols)
            typ = cols["type"]
            acl = cols["acl"]
            parentUserKey = cols["owner"]
        timeuuid = uuid.uuid1().bytes
        responseType = "L"
        # 1. add user to Likes list
        yield Db.insert(itemKey, "itemLikes", timeuuid, userKey)

        # 2. add users to the followers list of parent item
        yield Db.batch_insert(parent, "items", {"followers":{userKey:''}})

        # 3. update user's feed, feedItems, feed_*
        yield pushToFeed(userKey, timeuuid, itemKey, parent,
                         responseType, typ, parentUserKey, userKey)

        # 4. update feed, feedItems, feed_* of user's followers/friends (based on acl)
        yield pushToOthersFeed(userKey, timeuuid, itemKey, parent, acl,
                                responseType,typ, parentUserKey)

        # TODO: broadcast to followers of the items

        # 5. render parent item
        items = yield getItems(userKey, parent)
        args ={"comments":items}
        landing = not self._ajax
        yield  renderScriptBlock(request, "feed.mako", "feed", landing,
                            "#%s"%(parent), "set", **args)

    @defer.inlineCallbacks
    def _setUnlike(self, request):
        itemKey = utils.getRequestArg(request, "itemKey")
        parent =  utils.getRequestArg(request, "parent")
        parentUserKey = utils.getRequestArg(request, "parentUserId")
        userKey = request.getSession(IAuthInfo).username

        typ = utils.getRequestArg(request, "type")
        acl = utils.getRequestArg(request, "acl")

        if not (typ and acl and parentUserKey):
            cols = yield Db.get_slice(parent, "items",
                                      ["type", "acl", "owner"],
                                      super_column = "meta")
            cols = utils.columnsToDict(cols)
            typ = cols["type"]
            parentUserKey = cols["owner"]
            acl = cols["acl"]
        # 1. remove the user from likes list.
        yield Db.remove(itemKey, "itemLikes", userKey)

        # 2. Don't remove the user from followers list
        #    (use can also become follower by responding to item,
        #        so user can't be removed from followers list)

        # 3. delete from user's feed, feedItems, feed_*
        yield deleteFromFeed(userKey, itemKey, parent, typ)

        # 4. delete from feed, feedItems, feed_* of user's friends/followers
        yield deleteFromOthersFeed(userKey, itemKey, parent,
                                   typ, acl, parentUserKey)
        # 5. render parent item
        items = yield getItems(userKey, parent)
        args ={"comments":items}
        landing = not self._ajax
        yield  renderScriptBlock(request, "feed.mako", "feed", landing,
                            "#%s"%(parent), "set", **args)

    @defer.inlineCallbacks
    def _share(self, request, typ):
        meta = {}
        target = utils.getRequestArg(request, "target")
        if target:
            meta["target"] = target

        userKey = request.getSession(IAuthInfo).username
        cols = yield Db.get(userKey, "users", "name", "basic")
        username = utils.columnsToDict([cols])["name"]

        meta["owner"] = userKey
        meta["timestamp"] = "%s" % int(time.time())

        comment = utils.getRequestArg(request, "comment")
        if comment:
            meta["comment"] = comment

        parent = utils.getRequestArg(request, "parent")
        parent = parent if parent else ''
        if parent:
            meta["parent"] = parent

        url = utils.getRequestArg(request, "url")
        if typ == "link":
            meta["url"] =  url
        if typ:
            meta["type"] = typ

        acl = utils.getRequestArg(request, "acl")
        meta["acl"] = acl
        landing = not self._ajax

        parentUserKey = utils.getRequestArg(request, "parentUserId")
        meta["count"] = '0'
        meta["responses"] = ''
        itemKey = utils.getUniqueKey()
        timeuuid = uuid.uuid1().bytes
        meta["uuid"] = timeuuid
        followers = {userKey:''}
        responseType = "C" if parent else "I"

        # 1. add item to "items"
        yield Db.batch_insert(itemKey, "items", {'meta': meta,
                                                 'followers':followers})

        # 2. update user's feed, feedItems, feed_typ
        yield pushToFeed(userKey, timeuuid, itemKey, parent,
                         responseType, typ, parentUserKey, userKey)

        # 3. update user's followers/friends feed, feedItems, feed_typ
        yield pushToOthersFeed(userKey, timeuuid, itemKey, parent, acl,
                                responseType, typ, parentUserKey)

        if parent:
            #4.1.1 update count, followers, reponses of parent item
            cols = yield Db.get_slice(parent, "items",
                                        ['count', 'responses', 'owner'],
                                        super_column='meta')
            cols = utils.columnsToDict(cols)
            count = int(cols["count"])
            responses = cols["responses"]
            parentOwner = cols["owner"]
            delimiter = ',' if responses else ''
            responses += delimiter + itemKey

            if count %5 == 1:
                count = yield Db.get_count(parent, "itemResponses")
            parentMeta = {"count": str(count+1), "responses": responses }

            yield Db.batch_insert(parent, "items", {"meta": parentMeta,
                                                    "followers": followers})

            # 4.1.2 add item as response to parent
            yield Db.insert(parent, "itemResponses", itemKey, timeuuid)

            if parentOwner != userKey:
                # 4.1.3 update user's userItems, userItems_*
                userItemValue = ":".join([itemKey, parent, parentOwner])
                yield Db.insert(userKey, "userItems", userItemValue, timeuuid)
                yield Db.insert(userKey, "userItems_" + typ, userItemValue, timeuuid)

        else:
            # 4.2 update user's userItems, userItems_*
            userItemValue = ":".join([itemKey, "", ""])
            yield Db.insert(userKey, "userItems", userItemValue, timeuuid)
            yield Db.insert(userKey, "userItems_" + typ, userItemValue, timeuuid)

        # 5. render the parent item
        if parent:
            args ={"item":(comment, url, username, acl, itemKey, parent)}
            yield renderScriptBlock(request, "feed.mako", "updateComments", landing,
                                    "#%s_comment"%(parent), "append", **args)
        else:
            args = {"comments": [[[comment, url, username, itemKey, acl,
                                userKey, None, False]]]}
            yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                   "#user-feed", "prepend", **args)
        request.finish()

    def render_POST(self, request):
        if not self._ajax \
           or len(request.postpath) != 2 or request.postpath[0] != "share":
            request.redirect("/feed")
            request.finish()
            return server.NOT_DONE_YET
        self._share(request, request.postpath[1])
        return server.NOT_DONE_YET
