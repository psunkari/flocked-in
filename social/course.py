from twisted.internet   import defer
from telephus.cassandra import ttypes
from formencode         import compound

from social             import base, db, utils, errors, _, plugins
from social             import template as t
from social.core        import Feed
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args
from social.validators  import Validate, SocialSchema, Entity, SocialString
from social.core        import Group
from social.groups      import GroupFeed

class CourseResource(base.BaseResource):
    isLeaf = True

    @Validate(GroupFeed)
    @defer.inlineCallbacks
    def _renderForum(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        args["menuId"] = "courses"
        args["filterType"] = "trending"

        if script and landing:
            t.render(request, "course.mako", **args)
        elif script and appchange:
            t.renderScriptBlock(request, "course.mako", "layout",
                                landing, "#mainbar", "set", **args)
        if script:
            onload = "$$.files.init('sharebar-attach');"

            t.renderScriptBlock(request, "feed.mako", "share_block",
                                landing,  "#share-block", "set",
                                handlers={"onload": onload}, **args)
        if script:
            onload = ""
            t.renderScriptBlock(request, "course.mako", "feed", landing,
                                "#user-feed-wrapper", "set", True,
                                handlers={"onload": onload}, **args)

        group = data['id']
        start = data['start']
        itemType = data['type']

        #if user dont belong to this group show "Join Group" message
        isMember = yield db.get_count(group.id, "groupMembers", start=myId, finish=myId)
        isFollower = yield db.get_count(group.id, "followers", start=myId, finish=myId)
        columns = ["GI:%s" % (group.id), "GO:%s" % (group.id)]
        cols = yield db.get_slice(myId, "pendingConnections",  columns)
        pendingConnections = utils.columnsToDict(cols)

        args["groupId"] = group.id
        args["entities"] = base.EntitySet(group)
        args["isMember"] = True

        ##XXX: following should not be static
        args["pendingConnections"] = pendingConnections
        args["myGroups"] = [group.id] if isMember else []
        args["groupFollowers"] = {group.id: [myId]} if isFollower else {group.id: []}

        if script:
            feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                       feedId=group.id, start=start,
                                       itemType=itemType)
            args.update(feedItems)

        entities = base.EntitySet(group.admins.keys())
        yield entities.fetchData()
        for entityId in entities.keys():
            if entityId not in args['entities']:
                args['entities'][entityId] = entities[entityId]
        args['entities'].update(group)

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            t.renderScriptBlock(request, "group-feed.mako", "feed", landing,
                                "#user-feed", "set", True,
                                handlers={"onload": onload}, **args)

            for pluginType in plugins:
                plugin = plugins[pluginType]
                if hasattr(plugin, 'renderFeedSideBlock'):
                    yield plugins["event"].renderFeedSideBlock(request,
                                                    landing, group.id, args)

        else:
            t.render(request, "course.mako", **args)

    @Validate(GroupFeed)
    @defer.inlineCallbacks
    def _renderTopicPage(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        args["menuId"] = "courses"

        args["title"] = "API Introduction"

        id = data["id"]
        args["filterType"] = "qna"
        if script and landing:
            t.render(request, "townhall.mako", **args)
        elif script and appchange:
            t.renderScriptBlock(request, "townhall.mako", "layout",
                                landing, "#mainbar", "set", **args)
        if script:
            onload = "$$.files.init('sharebar-attach');"

            #t.renderScriptBlock(request, "townhall.mako", "summary",
            #                    landing, "#group-summary", "set", **args)
            t.renderScriptBlock(request, "feed.mako", "share_block",
                                landing,  "#share-block", "set",
                                handlers={"onload": onload}, **args)
            yield self._renderShareBlock(request, "status")

        if id !="":
            args["filterType"] = "discussions"
            onload = ""
            t.renderScriptBlock(request, "course.mako", "topic_feed", landing,
                                "#user-feed", "set", True,
                                handlers={"onload": onload}, **args)
            yield self._renderTopicPageDiscussions(request, data)
        else:
            if script:
                onload = ""
                t.renderScriptBlock(request, "townhall.mako", "feed", landing,
                                    "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)
        if not script:
            t.render(request, "townhall.mako", **args)

    @defer.inlineCallbacks
    def _renderTopicPageDiscussions(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        group = data['id']
        start = data['start']
        itemType = data['type']

        #if user dont belong to this group show "Join Group" message
        isMember = yield db.get_count(group.id, "groupMembers", start=myId, finish=myId)
        isFollower = yield db.get_count(group.id, "followers", start=myId, finish=myId)
        columns = ["GI:%s" % (group.id), "GO:%s" % (group.id)]
        cols = yield db.get_slice(myId, "pendingConnections",  columns)
        pendingConnections = utils.columnsToDict(cols)

        args["groupId"] = group.id
        args["entities"] = base.EntitySet(group)
        args["isMember"] = True

        ##XXX: following should not be static
        args["pendingConnections"] = pendingConnections
        args["myGroups"] = [group.id] if isMember else []
        args["groupFollowers"] = {group.id: [myId]} if isFollower else {group.id: []}

        if script:
            feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                       feedId=group.id, start=start,
                                       itemType=itemType)
            args.update(feedItems)

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            t.renderScriptBlock(request, "group-feed.mako", "feed", landing,
                                "#user-discussion-feed", "set", True,
                                handlers={"onload": onload}, **args)

        entities = base.EntitySet(group.admins.keys())
        yield entities.fetchData()
        for entityId in entities.keys():
            if entityId not in args['entities']:
                args['entities'][entityId] = entities[entityId]
        args['entities'].update(group)


    @defer.inlineCallbacks
    def _renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderForum(request)
        elif segmentCount == 1:
            d = self._renderTopicPage(request)

        return self._epilogue(request, d)

class CourseTopicResource(base.BaseResource):
    pass
