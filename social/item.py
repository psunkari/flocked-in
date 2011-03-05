import json

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from twisted.plugin     import getPlugins


from social             import base, Db, utils, plugins
from social.auth        import IAuthInfo
from social             import utils
from social.template    import render, renderScriptBlock
from social             import feed


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

            toFeed = True if itemType in ['status', 'poll'] else False

            yield self.renderItem(request, toFeed)


    @defer.inlineCallbacks
    def actOnItem(self, request):
        itemType = utils.getRequestArg(request, "type")
        convId = utils.getRequestArg(request, "id")
        if itemType in plugins:
            yield plugins[itemType].post(request)
        #TODO:
        yield self.renderItem(request, False)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d =  self.renderItem(request)
            def callback(res):
                request.finish()
            def errback(err):
                log.msg(err)
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET

    def render_POST(self, request):

        def callback(res):
            request.finish()
        def errback(err):
            log.msg(err)
            request.setResponseCode(500)
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'new':
            d =  self.createItem(request)
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        if segmentCount == 1 and request.postpath[0] == 'act':
            d =  self.actOnItem(request)
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
