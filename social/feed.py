
import time
import uuid

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base
from social.template    import render, renderDef, renderScriptBlock
from social.auth        import IAuthInfo
from social.constants import INFINITY

@defer.inlineCallbacks
def getItems(userKey, count=10):

    feedItems = yield Db.get_slice(userKey, "feed", count=count)
    feedItems = utils.columnsToDict(feedItems)

    items = yield Db.multiget_slice(feedItems.values(), "items", count=count)
    itemsMap = utils.multiSuperColumnsToDict(items)

    friends = yield utils.getFriends(userKey, count=INFINITY)
    subscriptions = yield utils.getSubscriptions(userKey, count= INFINITY)

    cols = yield Db.multiget_slice(feedItems.values(), "responses")
    responseMap = utils.multiColumnsToDict(cols)
    responseKeys = []
    for itemKey in responseMap:
        responseKeys.extend(responseMap[itemKey].values())

    responses = yield Db.multiget_slice(responseKeys, "items", count=count)
    responseDetails  = utils.multiSuperColumnsToDict(responses)

    posters = [itemsMap[itemKey]["meta"]["owner"] for itemKey in itemsMap]
    posters.extend([responseDetails[itemKey]["meta"]["owner"] for itemKey in responseDetails])
    #TODO: get profile pic info also.
    cols = yield Db.multiget_slice(posters, "users", super_column='basic',
                                        count=INFINITY)
    posterInfo = utils.multiColumnsToDict(cols)

    displayItems = []
    for itemKey in itemsMap:
        meta = itemsMap[itemKey]["meta"]
        acl = meta["acl"]
        owner = meta["owner"]
        if utils.checkAcl(userKey, acl, owner, friends, subscriptions):
            items = []
            comment = meta["comment"]
            url = meta.get("url", None)
            items.append([comment, url, posterInfo[owner]["name"], itemKey, acl])
            for responseId in responseMap.get(itemKey, {}).values():
                owner = responseDetails[responseId]["meta"]["owner"]
                comment = responseDetails[responseId]["meta"]["comment"]
                url = responseDetails[responseId]["meta"].get("url", None)
                name = posterInfo[owner]["name"]
                acl = responseDetails[responseId]["meta"]["acl"]
                items.append([comment, url, name, responseId, acl])
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
    def _share(self, request, typ):
        meta = {}
        target = utils.getRequestArg(request, "target")
        if target:
            meta["target"] = target

        userKey = request.getSession(IAuthInfo).username;
        meta["owner"] = userKey
        meta["timestamp"] = "%s" % int(time.time() * 1000)

        comment = utils.getRequestArg(request, "comment")
        if comment:
            meta["comment"] = comment

        parent = utils.getRequestArg(request, "parent")
        if parent:
            meta["parent"] = parent

        if typ == "link":
            meta["url"] = utils.getRequestArg(request, "url")

        acl = utils.getRequestArg(request, "acl")
        meta["acl"] = acl

        parentUserKey = utils.getRequestArg(request, "parentId")

        itemKey = utils.getRandomKey(userKey)
        yield Db.batch_insert(itemKey, "items", {'meta': meta})
        yield Db.insert(userKey, "userItems", itemKey, uuid.uuid1().bytes)
        yield Db.insert(userKey, "userItems_" + typ, itemKey, uuid.uuid1().bytes)
        if not parent:
            yield Db.insert(userKey, "feed", itemKey, uuid.uuid1().bytes)



        notifyUsers = yield utils.expandAcl(userKey, acl,  userKey2=parentUserKey)
        for key in notifyUsers:
            if parent:
                yield Db.insert(key, "feed", parent, uuid.uuid1().bytes)
                yield Db.insert(key, "feed_" + typ, parent, uuid.uuid1().bytes)
            else:
                yield Db.insert(key, "feed", itemKey, uuid.uuid1().bytes)
                yield Db.insert(key, "feed_" + typ, itemKey, uuid.uuid1().bytes)

        if parent:
            yield Db.insert(parent, "responses", itemKey, uuid.uuid1().bytes)

        request.finish()

    def render_POST(self, request):
        if not self._ajax \
           or len(request.postpath) != 2 or request.postpath[0] != "share":
            request.redirect("/feed")
            request.finish()
            return server.NOT_DONE_YET

        self._share(request, request.postpath[1])
        return server.NOT_DONE_YET
