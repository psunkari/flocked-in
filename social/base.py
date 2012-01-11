
import json
import urlparse
from functools              import wraps

from twisted.web            import resource, server, http
from twisted.internet       import defer

from social.isocial         import IAuthInfo
from social                 import db, utils, errors
from social.template        import render, renderScriptBlock, renderDef
from social.logging         import log


class BaseResource(resource.Resource):
    requireAuth = True
    _ajax = False

    def __init__(self, ajax=False):
        self._ajax = ajax

    @defer.inlineCallbacks
    def _getBasicArgs(self, request):
        auth = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        myId = auth.username
        orgKey = auth.organization
        isOrgAdmin = auth.isAdmin

        script = False if request.args.has_key('_ns') or\
                          request.getCookie('_ns') else True
        appchange = True if request.args.has_key('_fp') and self._ajax or\
                            not self._ajax and script else False

        cols = yield db.multiget_slice([myId, orgKey], "entities", ["basic"])
        cols = utils.multiSuperColumnsToDict(cols)

        me = cols.get(myId, None)
        org = cols.get(orgKey, None)
        args = {"myKey": myId, "orgKey": orgKey, "me": me,
                "isOrgAdmin": isOrgAdmin, "ajax": self._ajax,
                "script": script, "org": org, "myId": myId, "orgId": orgKey}

        if appchange:
            latest = yield utils.getLatestCounts(request, False)
            args["latest"] = latest

        defer.returnValue((appchange, script, args, myId))

    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
        try:
            failure.raiseException()
        except errors.BaseError, e:
            errorCode, errorBrief, shortErrorStr, fullErrorStr = e.errorData()
            log.err(failure)
        except Exception, e:
            fullErrorStr = """<p>Something went wrong when processing your
                request.  The incident got noted and we are working on it.</p>
                <p>Please try again after sometime.</p>"""
            errorCode = 500
            shortErrorStr = """Oops... Unable to process your request.
                Please try after sometime"""
            log.err(failure)

        log.info(fullErrorStr)
        referer = request.getHeader('referer')

        try:
            appchange, script, args, myId = yield self._getBasicArgs(request)
            ajax = self._ajax
            args["referer"] = referer

            if ajax and not appchange:
                request.setResponseCode(errorCode)
                request.write(shortErrorStr)
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



class APIBaseResource(resource.Resource):
    isLeaf = True

    def _ensureAccessScope(self, request, needed):
        token = request.apiAccessToken
        if not token:
            raise errors.PermissionDenied()

        if needed not in token.scope:
            raise errors.PermissionDenied()

        return token


    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
        try:
            failure.raiseException()
        except errors.BaseError, e:
            errorCode, errorBrief, shortErrorStr, fullErrorStr = e.errorData()
        except:
            errorCode = 500
            errorBrief = http.RESPONSES[500]

        log.info(failure)

        request.setResponseCode(errorCode, errorBrief)
        request.setHeader('content-type', 'application/json')
        responseObj = {'error': errorBrief, 'error_description': fullErrorStr}
        request.write(json.dumps(responseObj))


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


    def _success(self, request, httpCode, responseObj):
        request.setResponseCode(httpCode, http.RESPONSES[httpCode])
        request.setHeader('content-type', 'application/json')
        request.write(json.dumps(responseObj))


