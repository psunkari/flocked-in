
from twisted.web            import resource, server
from twisted.internet       import defer
from twisted.python         import log

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

        me = yield Db.get_slice(myKey, "entities", ["basic"])
        me = utils.supercolumnsToDict(me)

        args = {"myKey": myKey, "orgKey": orgKey, "me": me,
                "ajax": self._ajax, "script": script}
        defer.returnValue((appchange, script, args, myKey))

    def _epilogue(self, request, deferred=None):
        if deferred:
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            def callback(response):
                request.finish()
            deferred.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        else:
            pass    # TODO
