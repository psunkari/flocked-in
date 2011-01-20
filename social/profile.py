
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

    def _default(self):
        request.redirect("/profile")
        request.finish()

    @defer.inlineCallbacks
    def _connect(self, request):
        if not request.args.has_key("target"):
            self._default()
            return

        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username
        targetKey = request.args["target"][0]

        (myDomain, ign, myId) = myKey.partition("/u/")
        (targetDomain, ign, targetId) = targetKey.partition("/u/")

        # TODO: In future support friendly domains
        # to allow the network span across multiple domains
        if myDomain != targetDomain:
            self._default()
            return

        try:
            result = yield Db.get(myKey, "connections", targetKey)
            if result.column.value == "__local__":
                d1 = Db.insert(myKey, "connections", "", targetKey)
                d2 = Db.insert(targetKey, "connections", "", myKey)
                yield d1
                yield d2
        except ttypes.NotFoundException:
            d1 = Db.insert(myKey, "connections", "__remote__", targetKey)
            d2 = Db.insert(targetKey, "connections", "__local__", myKey)
            yield d1
            yield d2

    def render_POST(self, request):
        done = False
        if len(request.postpath) == 1:
            action = request.postpath[0]
            if action == "connect":
                self._connect(request)
                return server.NOT_DONE_YET

        self._default()

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
                                    wrap, "#leftbar", "set", **args)
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
