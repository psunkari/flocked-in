
import json

from twisted.internet   import defer
from twisted.web        import resource, http, util

from social             import db, utils, base, errors
from social.item        import APIItemResource


class _APIAccessToken():
    _user = None
    _org = None
    _scope = None

    def __init__(self, apiTokenData):
        self._user = apiTokenData["user_id"]
        self._org = apiTokenData["org_id"]
        self._scope = apiTokenData["scope"].split(' ')

    def _get_user(self):
        return self._user
    user = property(_get_user)

    def _get_org(self):
        return self._org
    org = property(_get_org)

    def _get_scope(self):
        return self._scope
    scope = property(_get_scope)


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
        accessTokenData = utils.columnsToDict(accessTokenData)
        if not accessTokenData:
            request.setHeader("WWW-Authenticate",
                              'Bearer realm="Flocked-in API", error="invalid_token"')
            defer.returnValue(errors.APIErrorPage(401, 'Invalid Access Token'))
        else:
            request.apiAccessToken = _APIAccessToken(accessTokenData)

        defer.returnValue(rsrc)

    def getChildWithDefault(self, path, request):
        match = None

        if path == "items":
            match = self._item

        if not match:
            return errors.APIErrorPage(404, http.RESPONSES[404])

        d = self._ensureAuth(request, match)
        return util.DeferredResource(d)
