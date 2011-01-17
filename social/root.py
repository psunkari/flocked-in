
from twisted.web            import resource, server
from twisted.internet       import defer

from social                 import Db, utils, base
from social.template        import render
from social.profile         import ProfileResource
from social.auth            import IAuthInfo


class _ActualRoot(base.BaseResource):
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
        if not self._ajax:
            self._render(request)
            return server.NOT_DONE_YET
        else:
            return ''


class RootResource(resource.Resource):
    def __init__(self):
        self._root = _ActualRoot()
        self._ajax = AjaxResource()
        self._profile = ProfileResource()

    def getChildWithDefault(self, path, request):
        if path == "" or path == "feed":
            return self._root
        elif path == "profile":
            return self._profile
        elif path == "ajax":
            return self._ajax
        else:
            return resource.NoResource("Page not found")


class AjaxResource(RootResource):
    def __init__(self):
        self._root = _ActualRoot(True)
        self._ajax = resource.NoResource("Page not found")
        self._profile = ProfileResource(True)
