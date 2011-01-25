
from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social.auth            import IAuthInfo
from social                 import Db, utils, base


class ProfileResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @defer.inlineCallbacks
    def _connect(self, request):
        targetKey = utils.getRequestArg(request, "target")
        if not targetKey:
            self._default(request)
            return

        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username

        (myDomain, ign, myId) = myKey.partition("/u/")
        (targetDomain, ign, targetId) = targetKey.partition("/u/")

        # TODO: In future support friendly domains
        # to allow the network span across multiple domains
        if myDomain != targetDomain:
            self._default(request)
            return

        circles = request.args["circle"]\
                  if request.args.has_key("circle") else ["__default__"]
        circlesMap = dict([(circle, '') for circle in circles])

        calls = None
        try:
            yield Db.get(myKey, "connections", "__local__", targetKey)
            d1 = Db.remove(myKey, "connections", "__local__", targetKey)
            d2 = Db.remove(targetKey, "connections", "__remote__", myKey)
            d3 = Db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            calls = defer.DeferredList([d1, d2, d3])
        except ttypes.NotFoundException:
            circlesMap["__remote__"] = ''
            d1 = Db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d2 = Db.insert(targetKey, "connections", "", "__local__", myKey)
            calls = defer.DeferredList([d1, d2])

        yield calls
        request.finish()

    @defer.inlineCallbacks
    def _disconnect(self, request):
        targetKey = utils.getRequestArg(request, "target")
        if not targetKey:
            self._default(request)
            return

        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username

        try:
            d1 = Db.remove(myKey, "connections", None, targetKey)
            d2 = Db.remove(targetKey, "connections", None, myKey)
            yield d1
            yield d2
        except ttypes.NotFoundException:
            pass

        request.finish()

    def render_POST(self, request):
        if len(request.postpath) == 1:
            action = request.postpath[0]
            if action == "connect":
                d = self._connect(request)
            elif action == "disconnect":
                d = self._disconnect(request)
            else:
                self._default(request)

        return server.NOT_DONE_YET

    def render_GET(self, request):
        d = self._render(request)
        def errback(err):
            log.err(err)
            request.setResponseCode(500)
            request.finish()
        d.addErrback(errback)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _render(self, request):
        (layout, fp, script, args) = self._getBasicArgs(request)

        myKey = args["myKey"]
        userKey = "/".join(request.postpath) if len(request.postpath) > 0 else myKey
        args["userKey"] = userKey

        detail = request.args['dt'][0]\
                 if request.args.has_key('dt') else 'notes'
        args["detail"] = detail

        cols = yield Db.multiget_slice([myKey, userKey], "users")
        args["me"] = utils.supercolumnsToDict(cols[myKey])
        if cols[userKey] and len(cols[userKey]):
            args["user"] = utils.supercolumnsToDict(cols[userKey])
        else:
            request.redirect("/feed")
            request.finish()
            return

        if layout and script:
            yield render(request, "profile.mako", **args)

        relation = Relation(myKey, userKey)
        args["relation"] = relation
        wrap = not self._ajax

        yield relation.isFriend()
        if script and fp:
            self._clearAllBlocks(request)
            yield renderScriptBlock(request, "layout.mako", "left",
                                    wrap, "#left", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "center_header",
                                    wrap, "#center-header", "set", **args)

        if script:
            yield renderScriptBlock(request, "profile.mako", "tabs", wrap,
                                    "#center-contents", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "content", wrap,
                                    "#center-contents", "append", **args)

        if script and layout:
            request.write("</body></html>")

        if not script:
            yield render(request, "profile.mako", **args)

        request.finish()
