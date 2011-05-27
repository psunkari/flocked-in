
import uuid
from email.utils        import formatdate

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, _, __, base, plugins
from social             import constants, errors
from social.feed        import getFeedItems
from social.template    import render, renderDef, renderScriptBlock
from social.isocial     import IAuthInfo
from social.relations   import Relation
from social.logging     import profile, dump_args


@profile
@defer.inlineCallbacks
@dump_args
def ensureTag(request, tagName, orgId=None):
    authInfo = request.getSession(IAuthInfo)
    myId = authInfo.username
    myOrgId = authInfo.organization if not orgId else orgId
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
    def _render(self, request, tagId):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        args["menuId"] = "tags"
        args["tagId"]=tagId
        prevDisplayedTag = request.getCookie('cu')
        request.addCookie('cu', tagId, path="/ajax/tags")

        if script and landing:
            yield render(request, "tags.mako", **args)

        appchange = appchange or not prevDisplayedTag
        if script and appchange:
            yield renderScriptBlock(request, "tags.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        newId = (prevDisplayedTag != tagId) or appchange
        if newId or not script:
            tagInfo = yield Db.get_slice(myOrgId, "orgTags", super_column=tagId)
            if not tagInfo:
                raise errors.InvalidTag()
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

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            yield renderScriptBlock(request, "tags.mako", "itemsLayout",
                                    landing, "#content", "set", True,
                                    handlers={"onload": onload}, **args)

        if not script:
            yield render(request, "tags.mako", **args)


    @defer.inlineCallbacks
    def _renderMore(self, request, start, tagId):
        tagItems = yield self._getTagItems(request, tagId, start=start)
        args = tagItems
        args["tagId"] = tagId

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        yield renderScriptBlock(request, "tags.mako", "items", False,
                                "#next-load-wrapper", "replace", True,
                                handlers={"onload": onload}, **args)

    @defer.inlineCallbacks
    def _listTags(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]

        start = utils.getRequestArg(request, 'start') or ''
        nextPageStart = ''
        prevPageStart = ''
        count = constants.PEOPLE_PER_PAGE
        toFetchCount = count + 1
        start = utils.decodeKey(start)

        appchange = appchange or request.getCookie('cu')
        request.addCookie('cu', '', path="/ajax/tags", expires=formatdate(0))

        args["menuId"] = "tags"
        if script and landing:
            yield render(request, "tags.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "tags.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "tags.mako", "header",
                                    landing, "#tags-header", "set", **args )

        tagsByName = yield Db.get_slice(myOrgId, "orgTagsByName", start=start, count=toFetchCount)
        tagIds = [x.column.value for x in tagsByName]

        if len(tagsByName) > count:
            nextPageStart = utils.encodeKey(tagsByName[-1].column.name)
            tagIds = tagIds[:-1]

        if start:
            prevCols = yield Db.get_slice(myOrgId, "orgTagsByName",
                                          start=start, reverse=True,
                                          count=toFetchCount)
            if len(prevCols) > 1:
                prevPageStart = utils.encodeKey(prevCols[-1].column.name)

        tags = {}
        if tagIds:
            tags = yield Db.get_slice(myOrgId, "orgTags", tagIds)
            tags = utils.supercolumnsToDict(tags)

        # TODO: We need an index of all tags that the user is following
        #       Probably convert the 'subscriptions' column family to 'Super'
        #       and have people and tags in the same column family.
        tagsFollowing = []
        if tagIds:
            cols = yield Db.multiget(tagIds, "tagFollowers", myId)
            tagsFollowing = [x for x in cols.keys() if cols[x]]
        
        args['tags'] = tags
        args['tagIds'] = tagIds
        args['tagsFollowing'] = tagsFollowing
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            if appchange:
                yield renderScriptBlock(request, "tags.mako", "tagsListLayout",
                                        landing, "#content", "set", **args)
            else:
                yield renderScriptBlock(request, "tags.mako", "listTags",
                                        landing, "#tags-wrapper", "set", **args)
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
            tagId = utils.getRequestArg(request, 'id');
            if tagId:
                d = self._render(request, tagId)
            else:
                d = self._listTags(request)
        elif segmentCount == 1 and request.postpath[0] == "more":
            tagId = utils.getRequestArg(request, 'id')
            start = utils.getRequestArg(request, 'start') or ""
            d = self._renderMore(request, start, tagId)

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

