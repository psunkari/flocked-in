
from twisted.web            import resource, server
from twisted.internet       import defer

from social                 import Db, utils
from social.template        import render
from social.profile         import ProfileResource
from social.auth            import IAuthInfo


class _ActualRoot(resource.Resource):
    isLeaf = True
    isAjax = False
    def __init__(self, isAjax=False):
        self.isAjax = isAjax

    @defer.inlineCallbacks
    def _render(self, request):
        authinfo = request.getSession(IAuthInfo)
        currentuser = authinfo.username
        col = yield Db.get_slice(currentuser, "users")
        myInfo = utils.supercolumnsToDict(col)

        args = {"me": myInfo}
        render(request, "index.mako", **args)

    def render_GET(self, request):
        if not self.isAjax:
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
