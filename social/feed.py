
import time
import uuid

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from telephus.cassandra import ttypes

from social             import Db, utils, base
from social.template    import render, renderDef, renderScriptBlock
from social.auth        import IAuthInfo
from social.constants import INFINITY


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
        yield pushToFeed(key, timeuuid,
                         itemKey, parentKey,
                         responseType, itemType)

@defer.inlineCallbacks
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType, itemType):

    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    yield Db.insert(userKey, "feed", parentKey, timeuuid)
    yield Db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)
    yield  updateFeedResponses(userKey, parentKey,
                               itemKey, timeuuid,
                               itemType, responseType)


@defer.inlineCallbacks
def updateFeedResponses(userKey, parentKey,
                        itemKey, timeuuid,
                        itemType, responseType):

    cols = yield Db.get_slice(userKey,
                              "feedItems",
                              super_column = parentKey,
                              reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)
    feedItemValue = ":".join([responseType, userKey, itemKey])
    if len(cols) >= 6:
        tmp, oldest = {}, None
        for tuuid, val in cols.items():
            tmp.setdefault(val.split(':')[0], []).append(tuuid)
            oldest = tuuid
        if len(tmp.get(responseType, [])) == 3:
            oldest = tmp[responseType][2]
        else:
            # remove the oldest column (it can be any responseType!))
            pass

        yield Db.remove(userKey, "feedItems", oldest, parentKey)
        yield Db.remove(userKey, "feed", oldest)
        yield Db.remove(userKey, "feed_"+itemType, oldest)
    yield Db.batch_insert(userKey, "feedItems", {parentKey:{timeuuid: feedItemValue}})


@defer.inlineCallbacks
def getItems(userKey, itemKey = None, count=10, start=''):
    def _generate_liked_text(userKey, likedBy):
        if likedBy:
            if userKey in likedBy and len(likedBy) == 1:
                return "you like this post", True
            elif userKey in likedBy and len(likedBy) >1:
                return "you and %s others like this post" %(len(likedBy)-1), True
            else:
                return "%s like this post" %(len(likedBy)), False
        else:
            return None, False
    """
    1. get the list of itemKeys from "feed" CF in reverse Chronological order
    2. get the details of item from "items" SCF
    3. get the response-itemKey for all items (frm step1) in Chronological Order.
    4. Get the details of response-itemKeys
    5. check acl:
        if user has access to the item add item, its responses to displayItems list;

    """

    #TODO: get latest feed items first
    if not itemKey:
        feedItems = yield Db.get_slice(userKey, "feed", count=count,
                                        start=start, reverse=True)
        feedItems = utils.columnsToDict(feedItems, ordered=True)

        #feedValues = [feedItems[supercolumn].values() for supercolumn in feedItems]
        #feedItemKeys = [x[0].split(":")[2] for x in feedValues]
    else:
        feedItemKeys = [itemKey]
    items = yield Db.multiget_slice(feedItemKeys, "items", count=count)
    itemsMap = utils.multiSuperColumnsToDict(items, ordered = True)

    friends = yield utils.getFriends(userKey, count=INFINITY)
    subscriptions = yield utils.getSubscriptions(userKey, count= INFINITY)

    cols = yield Db.multiget_slice(feedItemKeys, "itemResponses", count=INFINITY)
    responseMap = utils.multiColumnsToDict(cols, ordered=True)
    responseKeys = []
    for itemKey in responseMap:
        responseKeys.extend(responseMap[itemKey].values())

    responses = yield Db.multiget_slice(responseKeys, "items", count=count)
    responseDetails  = utils.multiSuperColumnsToDict(responses, ordered=True)
    posters = []
    for itemKey in itemsMap:
        posters.append(itemsMap[itemKey]["meta"]["owner"])

    #posters = [itemsMap[itemKey]["meta"]["owner"] for itemKey in itemsMap]
    posters.extend([responseDetails[itemKey]["meta"]["owner"] for itemKey in responseDetails])
    posters.extend([userKey])
    #TODO: get profile pic info also.
    cols = yield Db.multiget_slice(posters, "users", super_column='basic',
                                        count=INFINITY)
    posterInfo = utils.multiColumnsToDict(cols)

    displayItems = []
    for itemKey in feedItemKeys:
        meta = itemsMap[itemKey]["meta"]
        acl = meta["acl"]
        owner = meta["owner"]
        userCompKey = posterInfo[userKey]["org"]
        ownerCompKey = posterInfo[owner]["org"]

        if meta.get("type", None) in ["status", "link", "document"] \
            and utils.checkAcl(userKey, acl, owner, friends,
                                subscriptions, userCompKey, ownerCompKey):
            items = []
            comment = meta["comment"]
            url = meta.get("url", None)
            unlike = False
            cols = yield Db.get_slice(itemKey, "itemLikes")
            cols = utils.columnsToDict(cols)
            likedBy = cols.keys()
            liked_text, unlike = _generate_liked_text(userKey, likedBy)
            items.append([comment, url, posterInfo[owner]["name"], itemKey,
                            acl, owner, liked_text, unlike])
            for responseId in responseMap.get(itemKey, {}).values():
                owner = responseDetails[responseId]["meta"]["owner"]
                comment = responseDetails[responseId]["meta"]["comment"]
                url = responseDetails[responseId]["meta"].get("url", None)
                name = posterInfo[owner]["name"]
                acl = responseDetails[responseId]["meta"]["acl"]

                cols = yield Db.get_slice(responseId, "itemLikes")
                cols = utils.columnsToDict(cols)
                likedBy = cols.keys()

                liked_text, unlike = _generate_liked_text(userKey, likedBy)
                items.append([comment, url, name, responseId, acl,
                                liked_text, unlike])
            displayItems.append(items)
    defer.returnValue(displayItems)


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

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

        args["comments"] = yield getItems(myKey)
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
        parentUserKey = utils.getRequestArg(request, "parentId")
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
        yield pushToFeed(userKey, timeuuid, itemKey, parent, responseType, typ)

        # 4. update feed, feedItems, feed_* of user's followers/friends (based on acl)
        yield pushToOthersFeed(userKey, timeuuid, itemKey,
                               parent, acl, responseType,
                               typ, parentUserKey)

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
        parentUserKey = utils.getRequestArg(request, "parentId")
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
        meta["timestamp"] = "%s" % int(time.time() * 1000)

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

        parentUserKey = utils.getRequestArg(request, "parentId")
        meta["count"] = '0'
        meta["responses"] = ''
        itemKey = utils.getUniqueKey()
        timeuuid = uuid.uuid1().bytes
        meta["uuid"] = timeuuid
        followers = {userKey:''}
        responseType = "C" if parent else "S"
        feedItemValue = ":".join([responseType, userKey, itemKey])

        # 1. add item to "items"
        yield Db.batch_insert(itemKey, "items", {'meta': meta,
                                                 'followers':followers})

        # 2. update user's feed, feedItems, feed_typ
        yield pushToFeed(userKey, timeuuid, itemKey, parent, responseType, typ)

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
