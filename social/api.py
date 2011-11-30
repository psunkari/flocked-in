import uuid
from base64     import urlsafe_b64encode, urlsafe_b64decode
import hmac
import hashlib
import json
import re


from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _, fts
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log


class APIResource(base.BaseResource):
    isLeaf = True
    requireAuth = False

    @defer.inlineCallbacks
    def _renderFeedResource(self, request):
        valid = yield self._verifyAccessKey(request, "feed")
        if valid == 1:
            request.write(json.dumps({}))
        else:
            request.write(json.dumps({"fail":True}))

    def _profileResource(self, request):
        pass

    @defer.inlineCallbacks
    def _verifyAccessKey(self, request, scope):

        #XXX:If request came through GET, "read" scope, for POST, "write" scope
        access_token = utils.getRequestArg(request, 'access_token')
        if not access_token:
            bearer_header = request.getHeader("Authorization")
            if bearer_header and bearer_header.startswith("Bearer"):
                access_token = bearer_header.split("Bearer ", 1)[1]
            else:
                request.setResponseCode(401)
                request.setHeader("WWW-Authenticate", 'Bearer realm="flocked.in"')
                defer.returnValue(0)

        print access_token
        cols = yield db.get_slice(access_token, "oAccessTokens")
        cols = utils.supercolumnsToDict(cols)
        if "meta" not in cols:
            request.setResponseCode(401)
            error = "invalid_token"
            error_description = "The access token expired"
            request.setHeader("WWW-Authenticate", 'Bearer realm="flocked.in",\
                                                        error="%s",\
                                                        error_description="%s"' %(error, error_description)
                            )
            defer.returnValue(0)

        result = cols["meta"]
        stored_scope = result["scope"]
        if not stored_scope.endswith("+w") and scope.endswith("+w"):
            request.setResponseCode(403)
            error = "insufficient_scope"
            error_description = "The scope is beyond granted scope"
            request.setHeader("WWW-Authenticate", 'Bearer realm="flocked.in",\
                                                        error="%s",\
                                                        scope="%s",\
                                                        error_description="%s"' %(error, scope, error_description)
                            )
            defer.returnValue(0)

        print "Access Token Results %s" %(result)
        defer.returnValue(1)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            pass
        elif segmentCount == 1 and request.postpath[0] == "feed":
            request.setHeader("Access-Control-Allow-Origin", "*")
            d = self._renderFeedResource(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            pass
        elif segmentCount == 1 and request.postpath[0] == "feed":
            request.setHeader("Access-Control-Allow-Origin", "*")
            d = self._renderFeedResource(request)

        return self._epilogue(request, d)

    def render_OPTIONS(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            pass
        elif segmentCount == 1 and request.postpath[0] == "feed":
            print "In options!!!"
            request.setHeader("Access-Control-Allow-Origin", "http://localhost:9000")
            request.setHeader("Access-Control-Request-Method", "POST, GET, OPTIONS")
            request.setHeader("Access-Control-Request-Headers", "authorization")
            request.setHeader("Access-Control-Allow-Credentials", "true")

        return self._epilogue(request, d)
