from twisted.application    import service
from twisted.web            import resource, server

from social.template        import render


class RootResource(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        render(request, "index.html")
        return server.NOT_DONE_YET


class Service(service.Service):

    def root(self):
        r = resource.Resource()
        r.putChild("", RootResource())
        return r
