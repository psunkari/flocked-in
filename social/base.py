
from twisted.web            import resource, server
from twisted.internet       import defer

from social.isocial         import IAuthInfo
from social                 import Db, utils

class BaseResource(resource.Resource):
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    @defer.inlineCallbacks
    def _getBasicArgs(self, request):
        auth = request.getSession(IAuthInfo)
        myKey = auth.username
        orgKey = auth.organization

        script = False if request.args.has_key('_ns') or\
                          request.getCookie('_ns') else True
        appchange = True if request.args.has_key('_fp') and self._ajax or\
                            not self._ajax and script else False

        me = yield Db.get_slice(myKey, "users", ["basic"])
        me = utils.supercolumnsToDict(me)

        args = {"myKey": myKey, "orgKey": orgKey, "me": me,
                "ajax": self._ajax, "script": script}
        defer.returnValue((appchange, script, args, myKey))

    def _default(self, request):
        if not self._ajax:
            request.redirect("/feed")

        request.finish()

    def request_GET(self, request):
        self._clearAllBlocks()
        request.finish()
        return server.NOT_DONE_YET
