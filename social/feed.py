
from twisted.internet   import defer
from twisted.web        import server

from social             import Db, utils, base
from social.template    import render, renderDef, renderScriptBlock

class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @defer.inlineCallbacks
    def _render(self, request):
        (layout, fp, script, args) = self._getBasicArgs(request)

        myKey = args["myKey"]
        col = yield Db.get_slice(myKey, "users")
        me = utils.supercolumnsToDict(col)

        args["me"] = me

        if layout and script:
            yield render(request, "index.mako", **args)

        if script and fp:
            yield self._clearAllBlocks(request)

        if script and layout:
            request.write("</body></html>")

        if not script:
            yield render(request, "index.mako", **args)

        request.finish()

    def render_GET(self, request):
        self._render(request)
        return server.NOT_DONE_YET
