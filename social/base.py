
import traceback

from twisted.web            import resource, server
from twisted.internet       import defer
from twisted.python         import log

from social.isocial         import IAuthInfo
from social                 import db, utils
from social.template        import render, renderScriptBlock

_errors = {
    "Unauthorized": [ 
        """The URL you are trying to visit requires that you signin.
        Please <a href='/signin'>signin</a> if you already have a
        flocked-in account or proceed to the <a href='/'>homepage to
        know more about flocked-in and to signup</a>""",
        401, "Please signin"],
    "_default_": [
        """<p>Something went wrong when processing your request.
        The incident got noted and we are working on it.</p><p>Please try
        again after sometime.</p>""", 500, """Oops... Unable to process 
        your request. Please try after sometime"""]
}

class BaseResource(resource.Resource):
    requireAuth = True
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    @defer.inlineCallbacks
    def _getBasicArgs(self, request):
        auth = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        myKey = auth.username
        orgKey = auth.organization
        isOrgAdmin = auth.isAdmin

        script = False if request.args.has_key('_ns') or\
                          request.getCookie('_ns') else True
        appchange = True if request.args.has_key('_fp') and self._ajax or\
                            not self._ajax and script else False

        cols = yield db.multiget_slice([myKey, orgKey], "entities", ["basic"])
        cols = utils.multiSuperColumnsToDict(cols)

        me = cols.get(myKey, None)
        org = cols.get(orgKey, None)
        args = {"myKey": myKey, "orgKey": orgKey, "me": me,
                "isOrgAdmin": isOrgAdmin, "ajax": self._ajax,
                "script": script, "org": org}
        defer.returnValue((appchange, script, args, myKey))

    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
      try:
        appchange, script, args, myId = yield self._getBasicArgs(request)
        ajax = self._ajax

        errorData = _errors.get(failure.type.__name__, None)
        if not errorData:
            errorData = _errors.get('_default_')

        fullErrorStr, ajaxErrorCode, ajaxErrorStr = errorData

        if ajax and not appchange:
            request.setResponseCode(ajaxErrorCode)
            request.write(ajaxErrorStr)
        elif ajax and appchange:
            args["msg"] = fullErrorStr
            yield renderScriptBlock(request, "errors.mako", "layout",
                                not ajax, "#mainbar", "set", **args)
        else:
            args["msg"] = fullErrorStr
            if script:
                request.write("<script>$('body').empty();</script>")
            yield render(request, "errors.mako", **args)
      except Exception, e:
        log.msg(traceback.print_exc())
        log.err(e)

    def _epilogue(self, request, deferred=None):
        d = deferred if deferred else defer.fail(errors.NotFoundError())

        # Check for errors.
        d.addErrback(self._handleErrors, request)

        # Finally, close the connection if not already closed.
        def closeConnection(x):
            if not request._disconnected:
                request.finish()
        d.addBoth(closeConnection)
        return server.NOT_DONE_YET
