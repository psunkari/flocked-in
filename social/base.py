
from twisted.web            import resource, server

from social.auth            import IAuthInfo

class BaseResource(resource.Resource):
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    def _getBasicArgs(self, request):
        auth = request.getSession(IAuthInfo)
        myKey = auth.username

        layout = False if self._ajax else True
        script = False if request.args.has_key('_ns') else True
        fp = True if request.args.has_key('_fp') and not layout or\
                     layout and script else False
        args = {"myKey": myKey,
                "ajax": self._ajax, "script": script}

        return (layout, fp, script, args)

    def _clearAllBlocks(self, request):
        if self._ajax:
            request.write("clearAllBlocks();")
        else:
            request.write("<script type='application/javascript'>clearAllBlocks();</script>")

    def request_GET(self, request):
        self._clearAllBlocks()
        request.finish()
        return server.NOT_DONE_YET
