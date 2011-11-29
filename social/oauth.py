import uuid
import hmac
import hashlib
import json
import re
import urlparse
import urllib
from base64     import b64encode, b64decode

try:
    import cPickle as pickle
except:
    import pickle

from twisted.internet   import defer
from twisted.web        import resource, static, server

from social             import db, utils, base, errors, config, _, fts
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log


# Asks user to authorize the client.
class OAuthAuthorizeResource(base.BaseResource):
    isLeaf = True
    requireAuth = True

    CLIENT_MISSING = "The application did not supply the required credentials"
    CLIENT_INVALID = "The identity of the requesting application could not be verified"
    REDIRECTURI_MISMATCH = "The application requested an invalid redirection"
    CLIENT_GONE = "The application was removed or disabled"
    SIGNATURE_MISMATCH = "Please re-initiate authorization from the application"


    @defer.inlineCallbacks
    def _error(self, request, errstr):
        args  = {"error": True, "errstr": errstr, "title": "Authorization Error"}
        yield render(request, "oauth.mako", **args)


    def _buildFullUri(self, uri, queryStr):
        (scheme, netloc, path, query, fragment) = urlparse.urlsplit(uri)
        if query:
            query = "%s&%s" % (query, queryStr)
        else:
            query = queryStr
        return "%s://%s%s?%s" % (scheme, netloc, path, query)


    def _redirectOnError(self, request, uri, errstr, state):
        queryStr = urllib.urlencode({'error': errstr, 'state': state})
        redirectUri = self._buildFullUri(uri, queryStr)
        request.redirect(redirectUri)
        request.finish()


    def _redirectOnSuccess(self, request, uri, authCode, state):
        queryStr = urllib.urlencode({'code':authCode, 'state':state})
        redirectUri = self._buildFullUri(uri, queryStr)
        request.redirect(redirectUri)
        request.finish()


    @defer.inlineCallbacks
    def _renderAccessDialog(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        clientId = utils.getRequestArg(request, "client_id")
        if not clientId:
            yield self._error(request, self.CLIENT_MISSING)
            return

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            yield self._error(request, self.CLIENT_INVALID)
            return

        # We have a client now.
        clientMeta = client["meta"]

        # First verify that we were given a valid redirectUri
        redirectUri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)
        clientRedirectUri = b64decode(clientMeta['redirect'])
        if redirectUri and redirectUri != clientRedirectUri:
            yield self._error(request, self.REDIRECTURI_MISMATCH)
            return

        # All errors from here will be sent to the redirectUri
        redirectUri = clientRedirectUri
        state = utils.getRequestArg(request, 'state', sanitize=False) or ''
        errorType = None

        # Check response type
        responseType = utils.getRequestArg(request, 'response_type')
        if not responseType:
            errorType = 'invalid_request'
        elif responseType != 'code':
            errorType = 'unsupported_response_type'

        if not errorType:
            scopes = utils.getRequestArg(request, 'scope')
            scopes = scopes.split(' ')
            if scopes:
                clientScopes = clientMeta['scope'].split(' ')
                if [x for x in scopes if x not in clientScopes]:
                    errorType = 'access_denied'

        if errorType:
            self._redirectOnError(request, redirectUri, errorType, state)
            return

        # We need auth token for the form submission to go through.
        authToken = authinfo.token;

        # Render authorization form to the user
        args.update({"client": client, "client_id": clientId, "state": state,
                     "redirect_uri": redirectUri, "request_scopes": scopes,
                     "title": "Authorization Request", "token": authToken})

        # Signature to ensure that the hidden params aren't changed
        message = "%s:%s:%s:%s:%s" % \
                  (myId, clientId, ' '.join(scopes), redirectUri, state)
        checksum = hmac.new(myOrgId, message, hashlib.sha256)
        args.update({"signature":checksum.hexdigest()})
        yield render(request, "oauth.mako", **args)


    @defer.inlineCallbacks
    def _receiveUserAccess(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        allow = utils.getRequestArg(request, 'allow') == "true"
        state = utils.getRequestArg(request, 'state')
        scopes = utils.getRequestArg(request, 'scope')
        clientId = utils.getRequestArg(request, 'client_id')
        redirectUri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)
        signature = utils.getRequestArg(request, 'signature')

        # Check if signature is valid
        message = "%s:%s:%s:%s:%s" % \
                  (myId, clientId, scopes, redirectUri, state)
        checksum = hmac.new(myOrgId, message, hashlib.sha256)
        if signature != checksum.hexdigest():
            yield self._error(request, self.SIGNATURE_MISMATCH)
            return

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            yield self._error(request, self.CLIENT_GONE)
            return

        if allow:
            # Authcode must expire shortly after it is issued
            # We expire the authcode in 5 minutes?
            authCode = utils.getRandomKey()
            authMap = {"user_id": myId, "client_id": clientId,
                       "redirect_uri": b64encode(redirectUri),
                       "scope": scopes, "type": "auth"}
            yield db.batch_insert(authCode, "oAuthData", authMap, ttl=120)
            yield db.insert(myId, "entities", authCode, "apps", clientId, ttl=120)
            self._redirectOnSuccess(request, redirectUri, authCode, state)
        else:
            self._redirectOnError(request, redirectUri, "access_denied", state)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderAccessDialog(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._receiveUserAccess(request)

        return self._epilogue(request, d)




class OAuthTokenResource(base.BaseResource):
    isLeaf = True
    requireAuth = False
    _accessTokenExpiry = 1800       # 30 Minutes
    _refreshTokenExpiry = 3888000   # 45 Days


    def _error(self, request, errstr):
        request.setHeader('Content-Type', 'application/json;charset=UTF-8')
        request.write(json.dumps({'error': errstr}))


    def _success(self, request, accessToken, refreshToken):
        request.setHeader('Content-Type', 'application/json;charset=UTF-8')
        responseObj = {'access_token': accessToken,
                       'token_type': 'bearer',
                       'expires_in': self._accessTokenExpiry}
        if refreshToken:
            responseObj['refresh_token'] = refreshToken
        request.write(json.dumps(responseObj))


    @defer.inlineCallbacks
    def _generateAccessToken(self, request):
        grantType = utils.getRequestArg(request, 'grant_type')
        if not grantType:
            self._error(request, "invalid_request")
            return

        if grantType == "client_credentials":
            yield self._tokenForClientCred(request)
        elif grantType == "authorization_code":
            yield self._tokenForAuthCode(request)
        elif grantType == "refresh_token":
            yield self._tokenForAuthCode(request, refresh=True)


    @defer.inlineCallbacks
    def _tokenForAuthCode(self, request, refresh=False):
        clientId = utils.getRequestArg(request, 'client_id')
        clientSecret = utils.getRequestArg(request, 'client_secret')
        redirectUri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)
        scopes = utils.getRequestArg(request, 'scope')

        if refresh:
            authCode = utils.getRequestArg(request, 'refresh_token')
        else:
            authCode = utils.getRequestArg(request, 'code')

        # XXX: We should be checking for HTTP authentication before
        #      throwing an error in case of missing clientId and clientSecret.
        if not all([redirectUri, clientId, clientSecret, authCode]):
            self._error(request, "invalid_request")
            return

        grant = yield db.get_slice(authCode, "oAuthData")
        grant = utils.columnsToDict(grant)
        if not grant or grant['client_id'] != clientId or\
           grant['redirect_uri'] != b64encode(redirectUri) or\
           not (grant['type'] == 'auth' and not refresh or\
                grant['type'] == 'refresh' and refresh):
            self._error(request, "invalid_grant")
            return

        grantedScopes = grant['scope'].split(' ')
        if scopes:
            scopes = scopes.split(' ')
            if [x for x in scopes if x not in grantedScopes]:
                self._error(request, "invalid_scope")
                return
        else:
            scopes = grantedScopes

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client or client['meta']['secret'] != clientSecret:
            self._error(request, "invalid_client")
            return

        userId = grant["user_id"]
        accessToken = utils.getRandomKey()
        accessTokenData = {"user_id": userId, "type": "access",
                           "client_id": clientId,
                           "auth_code": authCode, "scope": " ".join(scopes)}
        yield db.batch_insert(accessToken, "oAuthData",
                              accessTokenData, ttl=self._accessTokenExpiry)

        refreshToken = utils.getRandomKey()
        refreshTokenData = {"user_id": userId, "type": "refresh",
                            "client_id": clientId,
                            "redirect_uri": grant["redirect_uri"],
                            "auth_code": authCode, "scope": grant["scope"]}
        yield db.batch_insert(refreshToken, "oAuthData",
                              refreshTokenData, ttl=self._refreshTokenExpiry)
        yield db.insert(userId, "entities", refreshToken, "apps",
                        clientId, ttl=self._refreshTokenExpiry)

        yield db.remove(authCode, "oAuthData")
        self._success(request, accessToken, refreshToken)


    def _tokenForClientCredentials(self, request):
        pass


    # XXX: For debugging only.
    #      Should be removed in production
    def render_GET(self, request):
        return self.render_POST(request)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._generateAccessToken(request)

        return self._epilogue(request, d)




class OAuthResource(resource.Resource):
    isLeaf = False

    def __init__(self):
        self._requestAuth = OAuthAuthorizeResource()
        self._requestToken = OAuthTokenResource()

    def getChildWithDefault(self, name, request):
        if name == "authorize":
            return self._requestAuth
        elif name == "token":
            return self._requestToken
        else:
            return self.getChild(name, request)

