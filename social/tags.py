
import uuid

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, _, __, base, plugins
from social.feed        import getFeedItems
from social.template    import render, renderDef, renderScriptBlock
from social.isocial     import IAuthInfo
from social.relations   import Relation
from social.logging     import profile, dump_args


@profile
@defer.inlineCallbacks
@dump_args
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

    def _getTagItems(self, request, tagId, start='', count=10):
        @defer.inlineCallbacks
        def getter(start='', count=12):
            items = yield Db.get_slice(tagId, "tagItems", count=count,
                                       start=start, reverse=True)
            defer.returnValue(utils.columnsToDict(items, ordered=True))

        return getFeedItems(request, getFn=getter, start=start,
                                 count=count, getReason=False)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        args["menuId"] = "tags"

        if script and landing:
            yield render(request, "tags.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "tags.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        tagId = utils.getRequestArg(request, "id")
        args["tagId"]=tagId
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
        start = utils.getRequestArg(request, "start") or ''

        tagItems = yield self._getTagItems(request, tagId, start=start)
        args.update(tagItems)
        fromFetchMore = ((not landing) and (not appchange) and start)

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            if fromFetchMore:
                yield renderScriptBlock(request, "tags.mako", "items", landing,
                                        "#next-load-wrapper", "replace", True,
                                        handlers={"onload": onload}, **args)
            else:
                yield renderScriptBlock(request, "tags.mako", "items",
                                        landing, "#tag-items", "set", True,
                                        handlers={"onload": onload}, **args)


    @defer.inlineCallbacks
    def _listTags(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        start = utils.getRequestArg(request, 'start') or ''
        nextPageStart = ''
        prevPageStart = ''
        count = 10
        toFetchCount = count + 1
        start = utils.decodeKey(start)

        args["menuId"] = "tags"
        if script and landing:
            yield render(request, "tags.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "tags.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        tags = yield Db.get_slice(myOrgId, "orgTagsByName", start=start, count= toFetchCount)
        tags = utils.columnsToDict(tags, ordered=True)

        if len(tags) > count:
            nextPageStart = utils.encodeKey(tags.keys()[-1])
            del tags[tags.keys()[-1]]

        if start:
            prevCols = yield Db.get_slice(myOrgId, "orgTagsByName",
                                          start=start, reverse=True,
                                          count= toFetchCount)
            if len(prevCols) > 1:
                prevPageStart = utils.encodeKey(prevCols[-1].column.name)

        tagsFollowing = []

        if tags:
            tagIds = tags.values()
            cols = yield Db.multiget_slice(tagIds, "tagFollowers")
            cols = utils.multiColumnsToDict(cols)
            for tagId in cols:
                if myId in cols[tagId]:
                    tagsFollowing.append(tagId)

        args['tags'] = tags
        args['tagsFollowing'] = tagsFollowing
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            yield renderScriptBlock(request, "tags.mako", "header",
                                    landing, "#tags-header", "set", args=[None], **args )

            yield renderScriptBlock(request, "tags.mako", "listTags",
                                    landing, "#content", "set", **args)

            yield renderScriptBlock(request, "tags.mako", "paging",
                                landing, "#tags-paging", "set", **args)

        if not script:
            yield render(request, "tags.mako", **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listTags(request)
        if segmentCount == 1 and request.postpath[0] == 'items':
            d = self._render(request)

        return self._epilogue(request, d)


    @profile
    @dump_args
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

