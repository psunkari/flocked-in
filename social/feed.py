
import time

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base
from social.template    import render, renderDef, renderScriptBlock
from social.auth        import IAuthInfo

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
        wrap = not self._ajax

        if layout and script:
            yield render(request, "feed.mako", **args)

        if script and fp:
            self._clearAllBlocks(request)
            yield renderScriptBlock(request, "layout.mako", "left",
                                    wrap, "#left", "set", **args)

        if script:
            yield renderScriptBlock(request, "feed.mako", "center_header",
                                    wrap, "#center-header", "set",
                                    handlers={"onload": "$('#share-form').submit(function(){$.post('/ajax' + $(this).attr('_action'), $(this).serialize(), null, 'script'); return false;});"},
                                    **args)
            yield self._renderShareBlock(request, "status")

        if script and layout:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)

        request.finish()

    @defer.inlineCallbacks
    def _renderShareBlock(self, request, type):
        wrap = not self._ajax
        renderDef = "share_status"

        if type == "link":
            renderDef = "share_link"
        elif type == "document":
            renderDef = "share_document"

        yield renderScriptBlock(request, "feed.mako", renderDef,
                                wrap, "#sharebar", "set", True,
                                handlers={"onload": "$('#sharebar-links .selected').removeClass('selected'); $('#sharebar-link-%s').addClass('selected'); $('#share-form').attr('_action', '/feed/share/%s');" % (type, type)})
        request.finish()

    def render_GET(self, request):
        if len(request.postpath) == 0:
            self._render(request)
        elif self._ajax and request.postpath[0] == "share":
            self._renderShareBlock(request, request.postpath[1])

        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _share(self, request, type):
        meta = {}
        target = utils.getRequestArg(request, "target")
        if target:
            meta["target"] = target

        userKey = request.getSession(IAuthInfo).username;
        meta["owner"] = userKey
        meta["timestamp"] = "%s" % int(time.time() * 1000)

        comment = utils.getRequestArg(request, "comment")
        if comment:
            meta["comment"] = comment

        parent = utils.getRequestArg(request, "parent")
        if parent:
            meta["parent"] = parent

        if type == "link":
            meta["url"] = utils.getRequestArg(request, "url")

        key = utils.getRandomKey(userKey)
        log.msg(key, meta)
        yield Db.batch_insert(key, "items", {'meta': meta})

        request.finish()

    def render_POST(self, request):
        if not self._ajax \
           or len(request.postpath) != 2 or request.postpath[0] != "share":
            request.redirect("/feed")
            request.finish()
            return server.NOT_DONE_YET

        self._share(request, request.postpath[1])
        return server.NOT_DONE_YET
