
from twisted.web            import resource, server

from social.template        import render
from social.profile         import ProfileResource


class _ActualRoot(resource.Resource):
    isLeaf = True
    isAjax = False
    def __init__(self, isAjax=False):
        self.isAjax = isAjax

    def render_GET(self, request):
        render(request, "index.mako")
        return server.NOT_DONE_YET


class RootResource(resource.Resource):
    def __init__(self):
        self._root = _ActualRoot()
        self._ajax = AjaxResource()
        self._profile = ProfileResource()

    def getChildWithDefault(self, path, request):
        if path == "":
            return self._root
        elif path == "profile":
            return self._profile
        elif path == "ajax":
            return self._ajax
        else:
            return resource.NoResource("Page not found")


class AjaxResource(RootResource):
    def __init__(self):
        self._root = resource.NoResource("Page not found")
        self._ajax = resource.NoResource("Page not found")
        self._profile = ProfileResource(True)
