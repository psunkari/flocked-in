import json

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from twisted.plugin     import getPlugins


from social             import base, Db, utils
from social.auth        import IAuthInfo
from social             import utils
from social.template    import render, renderScriptBlock
from social.isocial     import IItem
from social             import feed


class ItemResource(base.BaseResource):
    isLeaf = True
    def __init__(self, ajax=False):

        self.plugins = {}
        for plugin in getPlugins(IItem):
            self.plugins[plugin.itemType] = plugin
        base.BaseResource.__init__(self, ajax)

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
        col = yield Db.get(myKey, "users", super_column="basic")
        me = utils.supercolumnsToDict([col])
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
        plugin = None
        if itemType in self.plugins:
            plugin = self.plugins[itemType]

        # TODO: Fetch data required for rendering using the plugin
        if plugin:
            data = yield plugin.getRoot(convId, myKey)
            args.update(data)
            convOwner = data["items"][convId]["meta"]["owner"]
        else:
            conv = yield Db.get_slice(convId, "items", ['meta'])
            if not conv:
                raise errors.InvalidRequest()
            conv = utils.supercolumnsToDict(conv)
            args["items"] = {convId: conv}
            convOwner = conv['meta']['owner']
            owner = yield Db.get(convOwner, "users", super_column="basic")
            owner = utils.supercolumnsToDict([owner])
            args.update({"users":{convOwner:owner}})


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

        owner = yield Db.get(convOwner, "users", super_column="basic")
        owner = utils.supercolumnsToDict([owner])
        args["ownerId"] = convOwner
        args['owner'] = owner
        users[convOwner] = owner

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

        if itemType in self.plugins:
            plugin = self.plugins[itemType]
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
        if itemType in self.plugins:
            yield self.plugins[itemType].post(request)
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
