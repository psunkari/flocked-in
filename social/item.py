import json
import uuid
import time

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, Db, utils, feed, plugins
from social.auth        import IAuthInfo
from social.template    import render, renderScriptBlock


class ItemResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def renderItem(self, request, toFeed=False):
        (appchange, script, args) = self._getBasicArgs(request)
        landing = not self._ajax

        convId = utils.getRequestArg(request, "id")
        itemType = utils.getRequestArg(request, "type")
        if not convId:
            raise errors.MissingParam()

        args['convId'] = convId
        start = utils.getRequestArg(request, "start") or ''

        myKey = args['myKey']
        # base.mako needs "me" in args
        me = yield Db.get_slice(myKey, "users", ["basic"])
        me = utils.supercolumnsToDict(me)
        args["me"] = me

        if script and landing:
            yield render(request, "item.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "item.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users = {}
        items = {}
        args["users"] = users
        args["items"] = items
        toFetchUsers = set()

        plugin = plugins[itemType] if itemType in plugins else None
        if plugin:
            data, toFetchUsers, toFetchGroups = yield plugin.getRootData(args)
            args.update(data)
            if toFetchUsers:
                users = yield Db.multiget_slice(toFetchUsers, "users", ["basic"])
                users = utils.multiSuperColumnsToDict(users)
                args.update({"users": users})
            if toFetchGroups:
                groups = yield Db.multiget_slice(toFetchGroups, "groups", ["basic"])
                groups = utils.multiSuperColumnsToDict(groups)
                args.update({"groups": groups})
        else:
            conv = yield Db.get_slice(convId, "items", ['meta'])
            if not conv:
                raise errors.InvalidRequest()
            conv = utils.supercolumnsToDict(conv)
            convOwner = conv['meta']['owner']
            owner = yield Db.get(convOwner, "users", super_column="basic")
            owner = utils.supercolumnsToDict([owner])
            args.update({"users":{convOwner:owner}})
            args.update({"items":{convId: conv}})

        renderers = []

        if script:
            if plugin:
                args['toFeed'] = toFeed
                d =  plugin.renderRoot(request, convId, args)
                del args['toFeed']
            else:
                d = renderScriptBlock(request, "item.mako", "conv_root",
                                      landing, "#conv-root-%s" %(convId),
                                      "set", **args)
            renderers.append(d)

        convOwner = args["items"][convId]["meta"]["owner"]
        if convOwner not in args["users"]:
            owner = yield Db.get(convOwner, "users", super_column="basic")
            owner = utils.supercolumnsToDict([owner])
            args.update({"users": {convOwner: owner}})

        args["ownerId"] = convOwner

        if script:
            d = renderScriptBlock(request, "item.mako", "conv_owner",
                                  landing, "#conv-owner", "set", **args)
            renderers.append(d)

        itemResponses = yield Db.get_slice(convId, "itemResponses",
                                           start=start, reverse=True, count=25)
        responseKeys = []
        for response in itemResponses:
            userKey, responseKey = response.column.value.split(":")
            responseKeys.append(responseKey)
            toFetchUsers.add(userKey)

        d3 = Db.multiget_slice(responseKeys + [convId], "itemLikes")
        d2 = Db.multiget_slice(responseKeys, "items", ["meta"])
        d1 = Db.multiget_slice(toFetchUsers, "users", ["basic"])

        fetchedItems = yield d2
        fetchedUsers = yield d1
        myLikes = yield d3

        args["items"].update(utils.multiSuperColumnsToDict(fetchedItems))
        args["users"].update(utils.multiSuperColumnsToDict(fetchedUsers))
        args["myLikes"] = utils.multiColumnsToDict(myLikes)
        args["responses"] = {convId: responseKeys}

        if script:
            d = renderScriptBlock(request, "item.mako", 'conv_comments',
                                  landing, '#conv-comments-%s' % convId,
                                  'set', **args)
            renderers.append(d)

        # Wait till the item is fully rendered.
        yield defer.DeferredList(renderers)

        # TODO: Render other blocks


    @defer.inlineCallbacks
    def createItem(self, request):

        itemType = utils.getRequestArg(request, "type")
        myKey = request.getSession(IAuthInfo).username

        parent = None
        convOwner = myKey
        responseType = 'I'

        if itemType in plugins:
            plugin = plugins[itemType]
            convId, timeuuid, acl = yield plugin.create(request)

            request.args["id"] = [convId]
            userItemValue = ":".join([convId, "", ""])
            yield feed.pushToFeed(myKey, timeuuid, convId, parent, responseType,
                                  itemType, convOwner, myKey)

            yield feed.pushToOthersFeed(myKey, timeuuid, convId, parent, acl,
                                        responseType, itemType, convOwner)

            yield Db.insert(myKey, "userItems", userItemValue, timeuuid)
            if itemType in ["status", "link", "document"]:
                yield Db.insert(myKey, "userItems_%s"%(itemType) , userItemValue, timeuuid)

            toFeed = True if itemType in ['status', 'poll', 'event'] else False

            yield self.renderItem(request, toFeed)


    @defer.inlineCallbacks
    def actOnItem(self, request):
        itemType = utils.getRequestArg(request, "type")
        convId = utils.getRequestArg(request, "id")
        if itemType in plugins:
            yield plugins[itemType].post(request)
        #TODO:
        yield self.renderItem(request, False)


    @defer.inlineCallbacks
    def _like(self, request):
        itemId = utils.getRequestArg(request, "id")
        myId = request.getSession(IAuthInfo).username

        # Check if I already liked the item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
            raise errors.InvalidRequest()
        except ttypes.NotFoundException:
            pass

        # Get the item and the conversation
        item = yield Db.get(itemId, "items", super_column="meta")
        item = utils.supercolumnsToDict([item])

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield Db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
        else:
            convId = itemId
            conv = item

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # TODO: Check if I have access to that item before liking it!

        # Update the likes count
        likesCount = int(item.get("likesCount", "0")) + 1
        if likesCount % 5 == 0:
            likesCount = yield Db.get_count(itemId, "itemLikes")

        yield Db.insert(itemId, "items", str(likesCount), "likesCount", "meta")

        timeuuid = uuid.uuid1().bytes
        responseType = "L"
        # 1. add user to Likes list
        yield Db.insert(itemId, "itemLikes", timeuuid, myId)

        # 2. add users to the followers list of parent item
        yield Db.insert(convId, "items", "", myId, "followers")

        # 3. update user's feed, feedItems, feed_*
        yield feed.pushToFeed(myId, timeuuid, itemId, convId,
                              responseType, convType, convOwnerId, myId)

        # 4. update feed, feedItems, feed_* of user's followers/friends
        yield feed.pushToOthersFeed(myId, timeuuid, itemId, convId, convACL,
                                    responseType, convType, convOwnerId)

        # 5. Broadcast to followers of the items
        # TODO

        # Finally, update the UI
        # TODO

    @defer.inlineCallbacks
    def _unlike(self, request):
        itemId = utils.getRequestArg(request, "id")
        myId = request.getSession(IAuthInfo).username

        # Make sure that I liked this item
        try:
            cols = yield Db.get(itemId, "itemLikes", myId)
        except ttypes.NotFoundException:
            raise errors.InvalidRequest()

        # Get the item and the conversation
        item = yield Db.get(itemId, "items", super_column="meta")
        item = utils.supercolumnsToDict([item])

        convId = item["meta"].get("parent", None)
        conv = None
        if convId:
            conv = yield Db.get(convId, "items", super_column="meta")
            conv = utils.supercolumnsToDict([conv])
        else:
            convId = itemId
            conv = item

        convOwnerId = conv["meta"]["owner"]
        convType = conv["meta"]["type"]
        convACL = conv["meta"]["acl"]

        # 1. remove the user from likes list.
        yield Db.remove(itemId, "itemLikes", myId)

        # Update the likes count
        likesCount = int(item.get("likesCount", "1")) - 1
        if likesCount % 5 == 0:
            likesCount = yield Db.get_count(itemId, "itemLikes")
        yield Db.insert(itemId, "items", str(likesCount), "likesCount", "meta")

        responseType = 'L'
        # 2. Don't remove the user from followers list
        #    (use can also become follower by responding to item,
        #        so user can't be removed from followers list)

        # 3. delete from user's feed, feedItems, feed_*
        yield feed.deleteFromFeed(myId, itemId, convId,
                                  convType, myId, responseType)

        # 4. delete from feed, feedItems, feed_* of user's friends/followers
        yield feed.deleteFromOthersFeed(myId, itemId, convId, convType,
                                        convACL, convOwnerId, responseType)

        # Finally, update the UI
        # TODO

    @defer.inlineCallbacks
    def _comment(self, request):
        myId = request.getSession(IAuthInfo).username
        convId = utils.getRequestArg(request, "parent")
        comment = utils.getRequestArg(request, "comment")
        if not convId or not comment:
            raise errors.MissingParam()

        # 0. Fetch conversation and see if I have access to it.
        # TODO: Check ACL
        conv = yield Db.get_slice(convId, 'items', super_column='meta')
        conv = utils.columnsToDict(conv)
        convType = conv.get("type", "status")

        # 1. Create and add new item
        meta = {"owner": myId, "parent": convId, "comment": comment,
                "timestamp": str(int(time.time()))}
        followers = {myId: ''}
        itemId = utils.getUniqueKey()
        yield Db.batch_insert(itemId, "items", {'meta': meta,
                                                'followers': followers})

        # 2. Update response count and add myself to the followers of conv
        convOwnerId = conv["owner"]
        responseCount = int(conv.get("responseCount", "0")) + 1
        if responseCount % 5 == 0:
            responseCount = yield Db.get_count(convId, "itemResponses")

        convUpdates = {"responseCount": str(responseCount)}
        yield Db.batch_insert(convId, "items", {"meta": convUpdates,
                                                "followers": followers})

        # 3. Add item as response to parent
        timeUUID = uuid.uuid1().bytes
        yield Db.insert(convId, "itemResponses",
                        "%s:%s" % (myId, itemId), timeUUID)

        # 4. Update userItems and userItems_*
        userItemValue = ":".join([itemId, convId, convOwnerId])
        yield Db.insert(myId, "userItems", userItemValue, timeUUID)
        if plugins.has_key(convType) and plugins[convType].hasIndex:
            yield Db.insert(myId, "userItems_"+convType, userItemValue, timeUUID)

        # 5. Update my feed.
        yield feed.pushToFeed(myId, timeUUID, itemId, convId,
                              "C", convType, convOwnerId, myId)

        # 6. Push to other's feeds
        convACL = conv.get("acl", "company")
        yield feed.pushToOthersFeed(myId, timeUUID, itemId, convId,
                                    convACL, "C", convType, convOwnerId)

        # Finally, update the UI
        users = yield Db.get(myId, "users", super_column="basic")
        users = {myId: utils.supercolumnsToDict([users])}
        items = {itemId: {"meta": meta}}
        data = {"users": users, "items": items}
        d = yield renderScriptBlock(request, "item.mako", 'conv_comment',
                                    False, '#conv-comments-%s' % convId,
                                    'append', args=[convId, itemId], **data)


    @defer.inlineCallbacks
    def _likes(self, request):
        start = utils.getRequestArg();
        pass

    @defer.inlineCallbacks
    def _responses(self, request):
        pass


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            request.addCookie("_page", "item", path="/")
            d =  self.renderItem(request)
        elif segmentCount == 1:
            path = request.postpath[0]
            if path == "responses":
                self._responses(request)
            if path == "likes":
                self._likes(request)
            elif path == 'like' :
                d = self._like(request)
            elif path == 'unlike':
                d = self._unlike(request)

        if d:
            def callback(res):
                request.finish()
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        else:
            pass    # XXX: Throw error

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1:
            path = request.postpath[0]
            if path == 'new':
                d =  self.createItem(request)
            elif path == 'act':
                d =  self.actOnItem(request)
            elif path == 'comment':
                d = self._comment(request)

        if d:
            def callback(res):
                request.finish()
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()

            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        else:
            pass # XXX: 404 error
