
import json

from twisted.internet   import defer
from twisted.web        import resource, http, util

from social             import db, utils, base, errors
from social.item        import APIItemResource


class APIRoot(base.BaseResource):
    requireAuth = False


    def __init__(self):
        self._item = APIItemResource()


    @defer.inlineCallbacks
    def _ensureAuth(self, request, rsrc):
        accessToken = utils.getRequestArg(request, 'access_token')
        if not accessToken:
            authHeader = request.getHeader("Authorization")
            if authHeader and authHeader.startswith("Bearer"):
                accessToken = authHeader.split("Bearer ", 1)[1]
            else:
                request.setHeader("WWW-Authenticate", 'Bearer realm="Flocked-in API"')
                defer.returnValue(errors.APIErrorPage(401, http.RESPONSES[401]))

        accessTokenData = yield db.get_slice(accessToken, "oAuthData")
        accessTokenData = utils.supercolumnsToDict(accessTokenData)
        if not accessTokenData:
            request.setHeader("WWW-Authenticate",
                              'Bearer realm="Flocked-in API", error="invalid_token"')
            defer.returnValue(errors.APIErrorPage(401, 'Invalid Access Token'))
        else:
            request.apiAccessToken = accessTokenData

        defer.returnValue(rsrc)


    def getChildWithDefault(self, path, request):
        match = None

        if path == "items":
            match = self._item

        if not match:
            return errors.APIErrorPage(404, http.RESPONSES[404])

        d = self._ensureAuth(request, match)
        return util.DeferredResource(d)
