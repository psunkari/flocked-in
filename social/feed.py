
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
def getItems(userKey, itemKey = None, count=100):
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
    feedItems = yield Db.get_slice(userKey, "feed", count=count, reverse=True)
    feedItems = utils.columnsToDict(feedItems, ordered=True)
    feedItemsKeys = [itemKey] if itemKey else feedItems.values()
    items = yield Db.multiget_slice(feedItemsKeys, "items", count=count)
    itemsMap = utils.multiSuperColumnsToDict(items, ordered = True)

    friends = yield utils.getFriends(userKey, count=INFINITY)
    subscriptions = yield utils.getSubscriptions(userKey, count= INFINITY)

    cols = yield Db.multiget_slice(feedItemsKeys, "responses", count=INFINITY)
    responseMap = utils.multiColumnsToDict(cols, ordered=True)
    responseKeys = []
    for itemKey in responseMap:
        responseKeys.extend(responseMap[itemKey].values())

    responses = yield Db.multiget_slice(responseKeys, "items", count=count)
    responseDetails  = utils.multiSuperColumnsToDict(responses, ordered=True)

    posters = [itemsMap[itemKey]["meta"]["owner"] for itemKey in itemsMap]
    posters.extend([responseDetails[itemKey]["meta"]["owner"] for itemKey in responseDetails])
    #TODO: get profile pic info also.
    cols = yield Db.multiget_slice(posters, "users", super_column='basic',
                                        count=INFINITY)
    posterInfo = utils.multiColumnsToDict(cols)

    displayItems = []
    for itemKey in feedItemsKeys:
        meta = itemsMap[itemKey]["meta"]
        acl = meta["acl"]
        owner = meta["owner"]
        if utils.checkAcl(userKey, acl, owner, friends, subscriptions):
            items = []
            comment = meta["comment"]
            url = meta.get("url", None)
            unlike = False
            likedBy = itemsMap[itemKey].get("likes", {}).keys()
            liked_text, unlike = _generate_liked_text(userKey, likedBy)
            items.append([comment, url, posterInfo[owner]["name"], itemKey,
                            acl, owner, liked_text, unlike])
            for responseId in responseMap.get(itemKey, {}).values():
                owner = responseDetails[responseId]["meta"]["owner"]
                comment = responseDetails[responseId]["meta"]["comment"]
                url = responseDetails[responseId]["meta"].get("url", None)
                name = posterInfo[owner]["name"]
                acl = responseDetails[responseId]["meta"]["acl"]
                likedBy = responseDetails[responseId].get("likes", {}).keys()

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
            args["comments"]= yield getItems(myKey)
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
        userKey = request.getSession(IAuthInfo).username
        yield Db.insert(itemKey, "items", '', userKey, "likes")
        items = yield getItems(userKey, parent)
        args ={"comments":items}
        landing = not self._ajax
        yield  renderScriptBlock(request, "feed.mako", "feed", landing,
                            "#%s"%(parent), "set", **args)
    @defer.inlineCallbacks
    def _setUnlike(self, request):
        itemKey = utils.getRequestArg(request, "itemKey")
        parent =  utils.getRequestArg(request, "parent")
        userKey = request.getSession(IAuthInfo).username
        d1 = yield Db.remove(itemKey, "items", userKey, "likes")
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
        if parent:
            meta["parent"] = parent

        url = utils.getRequestArg(request, "url")
        if typ == "link":
            meta["url"] =  url

        acl = utils.getRequestArg(request, "acl")
        meta["acl"] = acl
        landing = not self._ajax

        parentUserKey = utils.getRequestArg(request, "parentId")

        itemKey = utils.getRandomKey(userKey)
        timeuuid = uuid.uuid1().bytes
        yield Db.batch_insert(itemKey, "items", {'meta': meta})
        yield Db.insert(userKey, "userItems", itemKey, timeuuid)
        yield Db.insert(userKey, "userItems_" + typ, itemKey, timeuuid)
        if not parent:
            yield Db.insert(userKey, "feed", itemKey, timeuuid)
            yield Db.insert(userKey, "feed_"+typ, itemKey, timeuuid)
            yield Db.insert(userKey, "feedReverseMap", timeuuid, itemKey)



        notifyUsers = yield utils.expandAcl(userKey, acl,  userKey2=parentUserKey)
        for key in notifyUsers:
            if parent:
                # if (key, parentId) is already in the feed dont insert it again.
                try:
                    cols = yield Db.get(key, "feedReverseMap", parent)
                except ttypes.NotFoundException:
                    yield Db.insert(key, "feed", parent, timeuuid)
                    yield Db.insert(key, "feed_" + typ, parent, timeuuid)
                    yield Db.insert(key, "feedReverseMap", timeuuid, parent)
            else:
                yield Db.insert(key, "feed", itemKey, timeuuid)
                yield Db.insert(key, "feed_" + typ, itemKey, timeuuid)
                yield Db.insert(key, "feedReverseMap", timeuuid, itemKey)

        if parent:
            yield Db.insert(parent, "responses", itemKey, uuid.uuid1().bytes)
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
