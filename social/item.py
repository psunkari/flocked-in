import json
from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, Db, utils
from social.auth        import IAuthInfo
from social             import utils
from social.template    import render, renderScriptBlock


class ItemResource(base.BaseResource):


    @defer.inlineCallbacks
    def renderItem(self, request):
        (appchange, script, args) = self._getBasicArgs(request)
        landing = not self._ajax

        convId = utils.getRequestArg(request, "id")
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

        conv = yield Db.get(convId, "items", super_column='meta')
        conv = utils.supercolumnsToDict([conv])
        items[convId] = conv
        ownerId = conv['meta']['owner']

        # TODO: Fetch data required for rendering using the plugin
        renderers = []
        if script:
            d = yield renderScriptBlock(request, "item.mako", "conv_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)
            renderers.append(d)

        owner = yield Db.get(ownerId, "users", super_column="basic")
        owner = utils.supercolumnsToDict([owner])
        args["ownerId"] = ownerId
        users[ownerId] = owner

        if script:
            d = yield renderScriptBlock(request, "item.mako", "conv_owner",
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
            d = yield renderScriptBlock(request, "item.mako", 'conv_comments',
                                        landing, '#conv-comments-%s' % convId,
                                        'set', **args)
            renderers.append(d)

        # Wait till the item is fully rendered.
        yield defer.DeferredList(renderers)

        # TODO: Render other blocks


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
        pass
