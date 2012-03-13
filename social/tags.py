
from telephus.cassandra import ttypes
from twisted.internet   import defer

from social             import db, utils, _, base
from social             import constants, errors, template as t
from social.core        import Feed
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args, log


@defer.inlineCallbacks
@dump_args
def _ensureTag(tagName, myId, orgId, presetTag=False):
    try:
        tagName = tagName.lower()
        c = yield db.get(orgId, "orgTagsByName", tagName)
        tagId = c.column.value
        c = yield db.get_slice(orgId, "orgTags", super_column=tagId)
        tag = utils.columnsToDict(c)
        if presetTag and not tag.get('isPreset', '') == 'True':
            yield db.insert(orgId, "orgPresetTags", tagId, tagName)

            yield db.insert(orgId, "orgTags", 'True', 'isPreset', tagId)
            tag['isPreset'] = 'True'
    except ttypes.NotFoundException:
        tagId = utils.getUniqueKey()
        tag = {"title": tagName, 'createdBy': myId}
        if presetTag:
            tag['isPreset'] = 'True'
        tagName = tagName.lower()
        yield db.batch_insert(orgId, "orgTags", {tagId: tag})
        yield db.insert(orgId, "orgTagsByName", tagId, tagName)
        if presetTag:
            yield db.insert(orgId, "orgPresetTags", tagId, tagName)

    defer.returnValue((tagId, tag))


@profile
@defer.inlineCallbacks
@dump_args
def ensureTag(request, tagName, orgId=None, presetTag=False):
    authInfo = request.getSession(IAuthInfo)
    myId = authInfo.username
    orgId = authInfo.organization if not orgId else orgId

    tagId, tag = yield _ensureTag(tagName, myId, orgId, presetTag)
    defer.returnValue((tagId, tag))


class TagsResource(base.BaseResource):
    isLeaf = True
    _templates = ['tags.mako']

    def _getTagItems(self, request, tagId, start='', count=10):
        itemsFromFeed = {}

        @defer.inlineCallbacks
        def getter(start='', count=12):
            items = yield db.get_slice(tagId, "tagItems", count=count,
                                       start=start, reverse=True)
            items = utils.columnsToDict(items, ordered=True)
            itemsFromFeed.update(items)
            defer.returnValue(items)

        @defer.inlineCallbacks
        def cleaner(convIds):
            deleteKeys = []
            for key, value in itemsFromFeed.items():
                if value in deleted:
                    deleteKeys.append(key)
            yield db.batch_remove({'tagItems': [tagId]}, names=deleteKeys)

        return Feed.get(request.getSession(IAuthInfo), getFn=getter,
                        cleanFn=cleaner, start=start, count=count,
                        getReasons=False)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        (tagId, tagInfo) = yield utils.getValidTagId(request, 'id')
        args["tags"] = tagInfo
        args["tagId"] = tagId
        args["tagFollowing"] = False
        args["menuId"] = "tags"

        if script and landing:
            t.render(request, "tags.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "tags.mako", "layout",
                                landing, "#mainbar", "set", **args)

        try:
            yield db.get(tagId, "tagFollowers", myId)
            args["tagFollowing"] = True
        except ttypes.NotFoundException:
            pass

        if script:
            t.renderScriptBlock(request, "tags.mako", "header",
                                landing, "#tags-header", "set", **args)
        start = utils.getRequestArg(request, "start") or ''

        tagItems = yield self._getTagItems(request, tagId, start=start)
        args.update(tagItems)

        if script:
            onload = """
                        (function(obj){$$.convs.load(obj);})(this);
                        $('form').html5form({messages: 'en'});
                     """
            t.renderScriptBlock(request, "tags.mako", "itemsLayout",
                                landing, "#content", "set", True,
                                handlers={"onload": onload}, **args)

        if not script:
            t.render(request, "tags.mako", **args)

    @defer.inlineCallbacks
    def _renderMore(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        (tagId, tagInfo) = yield utils.getValidTagId(request, 'id')
        start = utils.getRequestArg(request, 'start') or ""

        tagItems = yield self._getTagItems(request, tagId, start=start)
        args.update(tagItems)
        args["tagId"] = tagId

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        t.renderScriptBlock(request, "tags.mako", "items", False,
                            "#next-load-wrapper", "replace", True,
                            handlers={"onload": onload}, **args)

    @defer.inlineCallbacks
    def _listTags(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgId"]

        start = utils.getRequestArg(request, 'start') or ''
        nextPageStart = ''
        prevPageStart = ''
        count = constants.PEOPLE_PER_PAGE
        toFetchCount = count + 1
        start = utils.decodeKey(start)

        args["menuId"] = "tags"
        if script and landing:
            t.render(request, "tags.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "tags.mako", "layout",
                                landing, "#mainbar", "set", **args)

        if script:
            t.renderScriptBlock(request, "tags.mako", "header",
                                landing, "#tags-header", "set", **args)

        tagsByName = yield db.get_slice(myOrgId, "orgTagsByName",
                                        start=start, count=toFetchCount)
        tagIds = [x.column.value for x in tagsByName]

        if len(tagsByName) > count:
            nextPageStart = utils.encodeKey(tagsByName[-1].column.name)
            tagIds = tagIds[:-1]

        if start:
            prevCols = yield db.get_slice(myOrgId, "orgTagsByName",
                                          start=start, reverse=True,
                                          count=toFetchCount)
            if len(prevCols) > 1:
                prevPageStart = utils.encodeKey(prevCols[-1].column.name)

        tags = {}
        if tagIds:
            tags = yield db.get_slice(myOrgId, "orgTags", tagIds)
            tags = utils.supercolumnsToDict(tags)

        # TODO: We need an index of all tags that the user is following
        #       Probably convert the 'subscriptions' column family to 'Super'
        #       and have people and tags in the same column family.
        tagsFollowing = []
        if tagIds:
            cols = yield db.multiget(tagIds, "tagFollowers", myId)
            tagsFollowing = [x for x in cols.keys() if cols[x]]

        args['tags'] = tags
        args['tagIds'] = tagIds
        args['tagsFollowing'] = tagsFollowing
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            if appchange:
                t.renderScriptBlock(request, "tags.mako", "tagsListLayout",
                                    landing, "#content", "set", **args)
            else:
                t.renderScriptBlock(request, "tags.mako", "listTags",
                                    landing, "#tags-wrapper", "set", **args)
                t.renderScriptBlock(request, "tags.mako", "paging",
                                    landing, "#tags-paging", "set", **args)

        if not script:
            t.render(request, "tags.mako", **args)

    @defer.inlineCallbacks
    def _follow(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        tagId, tag = yield utils.getValidTagId(request, "id")

        count = int(tag[tagId].get('followersCount', 0))
        if count % 5 == 3:
            count = yield db.get_count(tagId, "tagFollowers")
        count = count + 1

        yield db.insert(tagId, "tagFollowers", '', myId)
        yield db.insert(orgId, "orgTags", str(count), "followersCount", tagId)

        args = {'tags': tag}
        args['tagsFollowing'] = [tagId]
        tag[tagId]['followersCount'] = count
        fromListTags = (utils.getRequestArg(request, '_pg') == '/tags/list')
        if fromListTags:
            t.renderScriptBlock(request, "tags.mako", "_displayTag",
                                False, "#tag-%s" % tagId, "replace",
                                args=[tagId], **args)
        else:
            t.renderScriptBlock(request, 'tags.mako', "tag_actions", False,
                                "#tag-actions-%s" % (tagId), "set",
                                args=[tagId, True, False])

    @defer.inlineCallbacks
    def _unfollow(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        tagId, tag = yield utils.getValidTagId(request, "id")

        count = int(tag[tagId].get('followersCount', 0))
        if count % 5 == 3:
            count = yield db.get_count(tagId, "tagFollowers")
        count = count - 1 if count > 0 else count

        yield db.remove(tagId, 'tagFollowers', myId)
        yield db.insert(orgId, "orgTags", str(count), "followersCount", tagId)

        tag[tagId]['followersCount'] = count
        args = {'tags': tag}
        args['tagsFollowing'] = []
        fromListTags = (utils.getRequestArg(request, '_pg') == '/tags/list')
        if fromListTags:
            t.renderScriptBlock(request, "tags.mako", "_displayTag",
                                False, "#tag-%s" % tagId, "replace",
                                args=[tagId], **args)
        else:
            t.renderScriptBlock(request, 'tags.mako', "tag_actions", False,
                                "#tag-actions-%s" % (tagId), "set",
                                args=[tagId, False, False])

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1:
            if request.postpath[0] == "list":
                d = self._listTags(request)
            elif request.postpath[0] == "more":
                d = self._renderMore(request)

        return self._epilogue(request, d)

    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount != 1:
            return self._epilogue(request, defer.fail(errors.NotFoundError()))
        action = request.postpath[0]
        if action == 'follow':
            d = self._follow(request)
        elif action == 'unfollow':
            d = self._unfollow(request)
        return self._epilogue(request, d)
