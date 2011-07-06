
import urlparse

from twisted.web            import resource, server
from twisted.internet       import defer
from twisted.python         import log

from social.isocial         import IAuthInfo
from social                 import db, utils, errors
from social.template        import render, renderScriptBlock, renderDef


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

        if appchange:
            latest = yield utils.getLatestCounts(request, False)
            args["latest"] = latest

        defer.returnValue((appchange, script, args, myKey))

    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
        try:
            failure.raiseException()
        except errors.BaseError, e:
            fullErrorStr, ajaxErrorCode, ajaxErrorStr = e.errorData()
            log.err(failure)
        except Exception, e:
            fullErrorStr = """<p>Something went wrong when processing your
                request.  The incident got noted and we are working on it.</p>
                <p>Please try again after sometime.</p>"""
            ajaxErrorCode = 500
            ajaxErrorStr = """Oops... Unable to process your request.
                Please try after sometime"""
            log.err(failure)

        log.msg(fullErrorStr)
        referer = request.getHeader('referer')

        try:
            appchange, script, args, myId = yield self._getBasicArgs(request)
            ajax = self._ajax
            args["referer"] = referer
         
            if ajax and not appchange:
                request.setResponseCode(ajaxErrorCode)
                request.write(ajaxErrorStr)
            elif ajax and appchange:
                args["msg"] = fullErrorStr
                yield renderScriptBlock(request, "errors.mako", "layout",
                                    not ajax, "#mainbar", "set", **args)
            else:
                if referer:
                    fromNetLoc = urlparse.urlsplit(referer)[1]
                    myNetLoc = urlparse.urlsplit(request.uri)[1]
                    if fromNetLoc != myNetLoc:
                        args["isDeepLink"] = True
                else:
                    args["isDeepLink"] = True
         
                args["msg"] = fullErrorStr
                if script:
                    request.write("<script>$('body').empty();</script>")
                yield render(request, "errors.mako", **args)
        except Exception, e:
            args = {"msg": fullErrorStr}
            yield renderDef(request, "errors.mako", "fallback", **args)

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
