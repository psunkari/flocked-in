
from twisted.web            import resource, server
from twisted.internet       import defer
from twisted.python         import log

from social.isocial         import IAuthInfo
from social                 import Db, utils

class BaseResource(resource.Resource):
    requireAuth = True
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    @defer.inlineCallbacks
    def _getBasicArgs(self, request):
        auth = request.getSession(IAuthInfo)
        myKey = auth.username
        orgKey = auth.organization
        isOrgAdmin = auth.isAdmin

        script = False if request.args.has_key('_ns') or\
                          request.getCookie('_ns') else True
        appchange = True if request.args.has_key('_fp') and self._ajax or\
                            not self._ajax and script else False

        cols = yield Db.multiget_slice([myKey, orgKey], "entities", ["basic"])
        cols = utils.multiSuperColumnsToDict(cols)

        me = cols.get(myKey, None)
        org = cols.get(orgKey, None)
        args = {"myKey": myKey, "orgKey": orgKey, "me": me,
                "isOrgAdmin": isOrgAdmin, "ajax": self._ajax,
                "script": script, "org": org}
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
            # TODO
            request.finish()
