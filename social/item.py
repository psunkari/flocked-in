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
            raise errors.NotFoundError()
        args['convId'] = convId
        start = utils.getRequestArg(request, "start") or ''

        myKey = args['myKey']
        col = yield Db.get_slice(myKey, "users", ["basic", "avatar"])
        me = utils.supercolumnsToDict(col)
        args["me"] = me

        if script and landing:
            yield render(request, "item.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "item.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users = set()
        responseKeys = []

        #TODO: use plugin to get the data
        conv = yield Db.get_slice(convId, "items", ['meta'])
        if not conv:
            log.err("ERROR: Invalid convId:%(convId)s" %locals())
            raise Exception("Invalid Request")
        conv = utils.supercolumnsToDict(conv)
        args["conv"] = conv
        convOwner = conv['meta']['owner']

        if script:
            renderRoot = yield renderScriptBlock(request, "item.mako",
                                                 "conv_root", landing,
                                                 "#conv-root-%s" %(convId),
                                                 "set", **args)


        d4 =  Db.get_slice(convOwner, "users", ["basic", "avatar"])

        owner = yield d4
        owner = utils.supercolumnsToDict(owner)
        args["ownerId"] = convOwner
        args['owner'] = owner

        if script:
            renderOwner = yield renderScriptBlock(request, "item.mako",
                                                  "conv_owner", landing,
                                                  "#conv-owner", "set", **args)


        itemResponses = yield Db.get_slice(convId, "itemResponses",
                                           start=start, reverse=True, count=25)

        for response in itemResponses:
            userKey_, responseKey = response.column.value.split(":")
            responseKeys.append(responseKey)
            users.add(userKey_)

        d3 = Db.multiget_slice(responseKeys + [convId], "itemLikes")
        d2 = Db.multiget_slice(responseKeys, "items", ["meta", "data"])
        d1 = Db.multiget_slice(users, "users", ["basic", "avatar"])

        items = yield d2
        users = yield d1
        itemLikes = yield d3
        itemLikes = utils.multiColumnsToDict(itemLikes)
        myLikes = [key for key in itemLikes if myKey in itemLikes[key].keys()]

        args["items"] = utils.multiSuperColumnsToDict(items)
        args["users"] = utils.multiSuperColumnsToDict(users)
        args["responses"] = responseKeys
        args["myLikes"] = myLikes

        if script:
            renderResponses = yield renderScriptBlock(request, "item.mako",
                                                      'conv_comments', landing,
                                                      '#conv-comments-%s' % convId, 'set',
                                                      **args)

        #TODO:
        #    itemMe = renderScriptBlock(request, "item.mako", "item_me",
        #                               landing, "#item-me", "set", **args)


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
