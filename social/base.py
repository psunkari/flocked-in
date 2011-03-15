
from twisted.web            import resource, server

from social.isocial         import IAuthInfo

class BaseResource(resource.Resource):
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    def _getBasicArgs(self, request):
        auth = request.getSession(IAuthInfo)
        myKey = auth.username
        orgKey = auth.organization

        script = False if request.args.has_key('_ns') or\
                          request.getCookie('_ns') else True
        appchange = True if request.args.has_key('_fp') and self._ajax or\
                            not self._ajax and script else False
        args = {"myKey": myKey, "orgKey": orgKey,
                "ajax": self._ajax, "script": script}

        return (appchange, script, args)

    def _default(self, request):
        if not self._ajax:
            request.redirect("/feed")

        request.finish()

    def request_GET(self, request):
        self._clearAllBlocks()
        request.finish()
        return server.NOT_DONE_YET
