
import uuid

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, _, __, base, plugins
from social.template    import render, renderDef, renderScriptBlock
from social.isocial     import IAuthInfo


@defer.inlineCallbacks
def ensureTag(request, tagName):
    authInfo = request.getSession(IAuthInfo)
    myId = authInfo.username
    myOrgId = authInfo.organization
    consistency = ttypes.ConsistencyLevel

    try:
        c = yield Db.get(myOrgId, "orgTagsByName",
                         tagName, consistency=consistency.QUORUM)
        tagId = c.column.value
        c = yield Db.get_slice(myOrgId, "orgTags", super_column=tagId,
                               consistency=consistency.QUORUM)
        tag = utils.columnsToDict(c)
    except ttypes.NotFoundException:
        tagId = utils.getUniqueKey()
        tag = {"title": tagName}
        yield Db.batch_insert(myOrgId, "orgTags",
                              {tagId: tag}, consistency=consistency.QUORUM)
        yield Db.insert(myOrgId, "orgTagsByName", tagId,
                        tagName, consistency=consistency.QUORUM)

    defer.returnValue((tagId, tag))



class TagsResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _getTagItems(self, request, tagId, count=10):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        toFetchItems = set()
        toFetchEntities = set()
        toFetchTags = set()
        args = {}
        convs = []

        tagItems = yield Db.get_slice(tagId, "tagItems",
                                      count=count, reverse=True)
        for item in tagItems:
            convs.append(item.column.value)
            toFetchItems.add(item.column.value)

        responses = {}
        itemResponses = yield Db.multiget_slice(toFetchItems, "itemResponses",
                                                count=2, reverse=True)
        for convId, comments in itemResponses.items():
            responses[convId] = []
            for comment in comments:
                userKey_, itemKey = comment.column.value.split(':')
                responses[convId].insert(0, itemKey)
                toFetchItems.add(itemKey)
                toFetchEntities.add(userKey_)

        items = yield Db.multiget_slice(toFetchItems, "items", ["meta", "tags"])
        items = utils.multiSuperColumnsToDict(items)
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

        fetchedEntities = yield Db.multiget(toFetchEntities, "entities", "basic")
        entities = utils.multiSuperColumnsToDict(fetchedEntities)

        tags = {}
        if toFetchTags:
            fetchedTags = yield Db.get_slice(myOrgId, "orgTags", toFetchTags)
            tags = utils.supercolumnsToDict(fetchedTags)

        fetchedLikes = yield Db.multiget(toFetchItems, "itemLikes", myId)
        myLikes = utils.multiColumnsToDict(fetchedLikes)

        data = {"entities": entities, "tags": tags,
                "items": items, "myLikes": myLikes,
                "responses": responses, "conversations": convs}
        args.update(data)
        defer.returnValue(args)


    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        if script and landing:
            yield render(request, "tags.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "tags.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        tagId = utils.getRequestArg(request, "id")
        request.addCookie('cu', tagId, path="/ajax/tags")
        if not tagId:
            raise errors.MissingParam()

        newId = (request.getCookie('cu') != tagId) or appchange
        if newId or not script:
            tagInfo = yield Db.get_slice(myOrgId, "orgTags", super_column=tagId)
            tagInfo = utils.columnsToDict(tagInfo)
            args["tags"] = {tagId: tagInfo}
            args["tagId"] = tagId
            args["tagFollowing"] = False
            try:
                yield Db.get(tagId, "tagFollowers", myKey)
                args["tagFollowing"] = True
            except ttypes.NotFoundException:
                pass

        if script and newId:
            yield renderScriptBlock(request, "tags.mako", "header",
                              landing, "#tags-header", "set", **args)

        tagItems = yield self._getTagItems(request, tagId)
        args.update(tagItems)

        if script:
            yield renderScriptBlock(request, "tags.mako", "items",
                                    landing, "#tag-items", "set", **args)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._render(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount != 1:
            raise errors.InvalidRequest()

        requestDeferred = utils.getValidTagId(request, "id")
        def callback((tagId, tag)):
            actionDeferred = None
            action = request.postpath[0]
            myId = request.getSession(IAuthInfo).username

            if action == "follow":
                actionDeferred = Db.insert(tagId, "tagFollowers", '', myId)
            elif action == "unfollow":
                actionDeferred = Db.remove(tagId, "tagFollowers", myId)
            else:
                raise errors.InvalidRequest()

            def renderActions(result):
                return renderScriptBlock(request, "tags.mako", "tag_actions",
                                False, "#tag-actions-%s" % tagId, "set",
                                args=[tagId], tagFollowing=(action=="follow"))
            actionDeferred.addCallback(renderActions)
            return actionDeferred

        requestDeferred.addCallback(callback)
        return self._epilogue(request, requestDeferred)
