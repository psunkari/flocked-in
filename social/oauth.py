import uuid
from base64     import urlsafe_b64encode, urlsafe_b64decode
import hmac
import hashlib
import json
import re

try:
    import cPickle as pickle
except:
    import pickle

from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _, fts
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log

     #+--------+                               +---------------+
     #|        |--(A)- Authorization Request ->|   Resource    |
     #|        |                               |     Owner     |
     #|        |<-(B)-- Authorization Grant ---|               |
     #|        |                               +---------------+
     #|        |
     #|        |                               +---------------+
     #|        |--(C)-- Authorization Grant -->| Authorization |
     #| Client |                               |     Server    |
     #|        |<-(D)----- Access Token -------|               |
     #|        |                               +---------------+
     #|        |
     #|        |                               +---------------+
     #|        |--(E)----- Access Token ------>|    Resource   |
     #|        |                               |     Server    |
     #|        |<-(F)--- Protected Resource ---|               |
     #+--------+                               +---------------+

    #For Authorization Grants, we support the following profiles:
    #    1 Authorization code
    #    2 client credentials

class OAuthUserResource(base.BaseResource):
    isLeaf = True
    requireAuth = True

    @defer.inlineCallbacks
    def _renderAccessDialog(self, request):
        # This dialog shows the user the access dialog whether to confirm or
        # deny a request started by a third party client
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        response_type = utils.getRequestArg(request, 'response_type')
        client_id = utils.getRequestArg(request, 'client_id')
        redirect_uri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)
        supplied_scope = utils.getRequestArg(request, 'scope')

        print "############" + supplied_scope

        #If the request fails due to a missing, invalid, or mismatching
        # redirection URI, or if the client identifier provided is invalid, the
        # authorization server SHOULD inform the resource owner of the error,
        # and MUST NOT automatically redirect the user-agent to the invalid
        # redirection URI.

        if not all([response_type, client_id, redirect_uri, supplied_scope]):
            raise errors.MissingParams(["Client ID", "Response Type",
                                        "Redirect URL", "scope"])

        args.update({"view":"fIn"})
        if script and landing:
            yield render(request, "oauth-server.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "oauth-server.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        cols = yield db.get_slice(client_id, "oAuthClients")
        cols = utils.supercolumnsToDict(cols)

        if "meta" in cols :
            #Check if the redirect_uri supplied matches one of the registered ones
            registered_redirect_uris = cols["meta"]["client_redirects"].split(":")
            if not urlsafe_b64encode(redirect_uri) in registered_redirect_uris:
                raise errors.PermissionDenied("Redirect URL Does not match")

            # We support only authentication profile 4.1. so check if response_type
            # is set to "code" otherwise fail.
            # Note profile 4.4 does not require authentication, hence not needed.
            if response_type != "code":
                error = "unsupported_response_type"
                Location = redirect_uri + "?error_code=%s" %error
                request.setResponseCode(307)
                request.setHeader('Location', Location)
            else:
                args.update(**cols["meta"])
                args.update({"client_id":client_id})
                args.update({"redirect_uri":redirect_uri})
                args.update({"supplied_scope":supplied_scope})

                #Generate a crypto signature to make sure that no hidden values sent
                # to the UI is being tampered with
                signature_message = "%s:%s:%s" %(client_id, myId, urlsafe_b64encode(redirect_uri))
                digest_maker = hmac.new(myOrgId, signature_message, hashlib.sha256)
                signature = digest_maker.hexdigest()
                args.update({"signature":signature})

                if appchange and script:
                    yield renderScriptBlock(request, "oauth-server.mako",
                                            "access_layout", landing, "#center",
                                            "set", **args)
        else:
            raise errors.InvalidItem("Application", client_id)

    @defer.inlineCallbacks
    def _receiveUserAccess(self, request):
        # This handles the response received from the user from the above dialog.
        # User either accepts or rejects a client app request and accordingly
        # the cb is called with auth_code or error
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        client_id = utils.getRequestArg(request, 'client_id')
        redirect_uri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)
        allow_access = utils.getRequestArg(request, 'allow_access')
        received_scope = utils.getRequestArg(request, 'scope')

        if not all([client_id, redirect_uri, allow_access, received_scope]):
            raise errors.MissingParams(["Client ID", "Redirect URI", "User Permission", "Scope"])

        # Check if signature is valid and whether client_id + user id +
        # redirect url match
        recieved_signature = utils.getRequestArg(request, 'signature')
        signature_message = "%s:%s:%s" %(client_id, myId, urlsafe_b64encode(redirect_uri))
        digest_maker = hmac.new(myOrgId, signature_message, hashlib.sha256)
        generated_signature = digest_maker.hexdigest()

        if generated_signature != recieved_signature:
            raise errors.PermissionDenied("Signature Does not match")

        cols = yield db.get_slice(client_id, "oAuthClients")
        cols = utils.supercolumnsToDict(cols)
        if "meta" not in cols:
            raise errors.PermissionDenied("Application does not exist")

        client_redirects = cols['meta']['client_redirects'].split(":")
        if urlsafe_b64encode(redirect_uri) not in client_redirects:
            raise errors.PermissionDenied("Redirect URI does not match")

        #The scope received from this screen will have to be a subset of the
        # originally registered scopes. So app cannot ask for more scopes than
        # he has registered for.
        allowed_entitites_in_scope = ("feed", "profile", "people")
        client_scope = pickle.loads(cols['meta']['client_scope'])
        received_scopes = received_scope.split(" ")
        scope_check = True
        for scope in received_scopes:
            scope_entity = scope.rsplit("_w")[0]
            if not scope.startswith(allowed_entitites_in_scope) or \
                    scope_entity not in allowed_entitites_in_scope:
                error = "invalid_scope"
                Location = redirect_uri + "?error_code=%s" %error
                scope_check = False
                break
            client_scope_entity_weight = client_scope[scope_entity]

            if scope.endswith("_w"):
                supplied_scope_entity_weight = 3
            else:
                supplied_scope_entity_weight = 1

            print "Saved weight is " + `client_scope_entity_weight`
            print "Supplied weight is " + `supplied_scope_entity_weight`

            if supplied_scope_entity_weight <= client_scope_entity_weight:
                continue
            else:
                scope_check = False
                error = "access_denied"
                Location = redirect_uri + "?error_code=%s" %error
                break

        if allow_access == "true" and scope_check:
            #The authorization code generated by the
            # authorization server.  The authorization code MUST expire
            # shortly after it is issued to mitigate the risk of leaks.  A
            # maximum authorization code lifetime of 10 minutes is
            # RECOMMENDED.  The client MUST NOT use the authorization code
            # more than once.  If an authorization code is used more than
            # once, the authorization server MUST deny the request and SHOULD
            # attempt to revoke all tokens previously issued based on that
            # authorization code.  The authorization code is bound to the
            # client identifier and redirection URI.

            #XXX: Check if user has signed up for this application
            auth_code = utils.getRandomKey()
            print "Authorization Code is " + `auth_code`
            auth_map = {
                        "user_id":myId,
                        "client_id":client_id,
                        "client_redirect_uri":urlsafe_b64encode(redirect_uri),
                        "client_scope":received_scope
                        }
            yield db.batch_insert(auth_code, "oAuthorizationCodes",
                                  {"meta":auth_map}, ttl=120)
            Location = redirect_uri + "?code=%s" %auth_code
        elif allow_access == "false":
            #error
            #      REQUIRED.  A single error code from the following:
            #      invalid_request
            #            The request is missing a required parameter, includes an
            #            unsupported parameter value, or is otherwise malformed.
            #      unauthorized_client
            #            The client is not authorized to request an authorization
            #            code using this method.
            #      access_denied
            #            The resource owner or authorization server denied the
            #            request.
            #      unsupported_response_type
            #            The authorization server does not support obtaining an
            #            authorization code using this method.
            #      invalid_scope
            #            The requested scope is invalid, unknown, or malformed.
            #      server_error
            #            The authorization server encountered an unexpected
            #            condition which prevented it from fulfilling the request.
            #      temporarily_unavailable
            #            The authorization server is currently unable to handle
            #            the request due to a temporary overloading or maintenance
            #            of the server.
            error = "access_denied"
            Location = redirect_uri + "?error_code=%s" %error
        else:pass
            #if script:
            #    request.write("window.location.href = '%s'" %Location)
            #else:
            #    request.setResponseCode(303)
            #    request.setHeader('Location', Location)

        if script:
            request.write("window.location.href = '%s'" %Location)
        else:
            request.setResponseCode(303)
            request.setHeader('Location', Location)

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

    @defer.inlineCallbacks
    def _generateAccessToken(self, request):
        #XXX:Since this method will be called via an independent POST request
        # and no session information will be stored, move this to another
        # resource with require auth set to False.
        #(appchange, script, args, myId) = yield self._getBasicArgs(request)
        #landing = not self._ajax

        grant_type = utils.getRequestArg(request, 'grant_type')

        if not grant_type:
            #XXX: Call the cb with error param
            raise errors.MissingParams(["Grant Type"])

        #A public client that was not issued a client password MAY use the
        #"client_id" request parameter to identify itself when sending
        #requests to the token endpoint.

        #Confidential clients, clients issued client credentials, or clients
        #assigned other authentication requirements MUST authenticate with the
        #authorization server as described in Section 2.3 when making requests
        #to the token endpoint.

        if grant_type == "client_credentials":
            yield self._renderAccessTokenProfile44(request)
        elif grant_type == "authorization_code":
            yield self._renderAccessTokenProfile41(request)

    @defer.inlineCallbacks
    def _renderAccessTokenProfile41(self, request):
        auth_code = utils.getRequestArg(request, 'code')
        redirect_uri = utils.getRequestArg(request, 'redirect_uri', sanitize=False)

        if not all([redirect_uri, auth_code]):
            raise errors.MissingParams([])

        cols = yield db.get_slice(auth_code, "oAuthorizationCodes")
        cols = utils.supercolumnsToDict(cols)

        if "meta" not in cols:
            error = "invalid_grant"
            request.setResponseCode(303)
            Location = redirect_uri + "?error_code=%s" %error
            request.setHeader('Location', Location)
            defer.returnValue(0)

        stored_client_id = cols["meta"]["client_id"]
        stored_redirect_uri = cols["meta"]["client_redirect_uri"]
        redirect_uri = urlsafe_b64encode(redirect_uri)

        #Check if client is public or private. A client is public if no
        # password has been set

        #Check if client_id has been supplied:
        client_id = utils.getRequestArg(request, 'client_id')
        print client_id
        if client_id:
            print "Good Public Client"
            #Check if auth code supplied was mapped to this client_id
            if stored_client_id != client_id:
                # Client id mismatch, fail this request
                error = "invalid_client"
                request.setResponseCode(303)
                Location = redirect_uri + "?error_code=%s" %error
                request.setHeader('Location', Location)
                defer.returnValue(0)
            else:
                #Auth code was mapped to this client id. Now check its redirect
                # uri also
                if stored_redirect_uri != redirect_uri:
                    error = "invalid_client"
                    request.setResponseCode(303)
                    Location = redirect_uri + "?error_code=%s" %error
                    request.setHeader('Location', Location)
                    defer.returnValue(0)
        else:
            #client id was not supplied, so ensure it has an authorization header
            # if it was registered as a private client.
            token_client_id = cols["meta"]["client_id"]
            client_cols = yield db.get_slice(token_client_id, "oAuthClients")

            client_cols = utils.supercolumnsToDict(client_cols)
            token_client_password = client_cols["meta"]["client_password"]
            if token_client_password != "":
                #Private Client, Check for Auth header
                print "Private Client"
                auth_header = request.getHeader("Authorization")
                if auth_header is None:
                    request.setResponseCode(401)
                    request.setHeader("WWW-Authenticate", 'Basic')
                    defer.returnValue(0)
                else:
                    client_password = auth_header.split("Basic ", 1)[1]
                    if token_client_password != client_password:
                        error = "invalid_grant"
                        request.setResponseCode(303)
                        Location = redirect_uri + "?error_code=%s" %error
                        request.setHeader('Location', Location)
                        defer.returnValue(0)
                    #Passwords have matched, now check redirect uri also
                    if stored_redirect_uri != redirect_uri:
                        error = "invalid_grant"
                        request.setResponseCode(303)
                        Location = redirect_uri + "?error_code=%s" %error
                        request.setHeader('Location', Location)
                        defer.returnValue(0)
            else:
                #Public Client with no id, match the redirect uri. Worst case client
                print "Bad Public Client"
                if stored_redirect_uri != redirect_uri:
                    error = "invalid_client"
                    request.setResponseCode(303)
                    Location = redirect_uri + "?error_code=%s" %error
                    request.setHeader('Location', Location)
                    defer.returnValue(0)


        #4.1.3. Access Token Request
        #
        #
        #   The client makes a request to the token endpoint by adding the
        #   following parameters using the "application/x-www-form-urlencoded"
        #   format in the HTTP request entity-body:
        #
        #   grant_type
        #         REQUIRED.  Value MUST be set to "authorization_code".
        #   code
        #         REQUIRED.  The authorization code received from the
        #         authorization server.
        #   redirect_uri
        #         REQUIRED, if the "redirect_uri" parameter was included in the
        #         authorization request as described in Section 4.1.1, and their
        #         values MUST be identical.
        #
        #   If the client type is confidential or the client was issued client
        #   credentials (or assigned other authentication requirements), the
        #   client MUST authenticate with the authorization server as described
        #   in Section 3.2.1.
        #
        #   For example, the client makes the following HTTP request using
        #   transport-layer security (extra line breaks are for display purposes
        #   only):
        #
        #
        #     POST /token HTTP/1.1
        #     Host: server.example.com
        #     Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW
        #     Content-Type: application/x-www-form-urlencoded;charset=UTF-8
        #
        #     grant_type=authorization_code&code=SplxlOBeZQQYbYS6WxSbIA
        #     &redirect_uri=https%3A%2F%2Fclient%2Eexample%2Ecom%2Fcb

        #Generate an access Key, remove the auth code from oAuthorizationCodes
        # XXX:Insert access key record into oAuthCode2Token for security reasons
        # insert access key into oAccessTokens

        access_token = utils.getRandomKey()
        yield db.remove(auth_code, "oAuthorizationCodes")
        access_map = {
                    "user_id":cols["meta"]["user_id"],
                    "client_id":cols["meta"]["client_id"],
                    "auth_code":auth_code,
                    "scope":cols["meta"]["client_scope"]
                    }
        print "Generated Access Token %s" %access_token

        yield db.batch_insert(access_token, "oAccessTokens",
                              {"meta":access_map}, ttl=120)
        token_response = {"access_token":access_token,
                          "token_type":"Bearer",
                          "expires_in":120,
                          "scope":cols["meta"]["client_scope"]}
        request.setHeader("Content-Type", "application/json;charset=UTF-8")
        request.write(json.dumps(token_response))

    @defer.inlineCallbacks
    def _renderAccessTokenProfile44(self, request):

        scope = utils.getRequestArg(request, 'scope')

        #4.4.2. Access Token Request
        #
        #
        #   The client makes a request to the token endpoint by adding the
        #   following parameters using the "application/x-www-form-urlencoded"
        #   format in the HTTP request entity-body:
        #
        #   grant_type
        #         REQUIRED.  Value MUST be set to "client_credentials".
        #   scope
        #         OPTIONAL.  The scope of the access request as described by
        #         Section 3.3.
        #
        #   The client MUST authenticate with the authorization server as
        #   described in Section 3.2.1.
        #
        #   For example, the client makes the following HTTP request using
        #   transport-layer security (extra line breaks are for display purposes
        #   only):
        #
        #
        #     POST /token HTTP/1.1
        #     Host: server.example.com
        #     Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW
        #     Content-Type: application/x-www-form-urlencoded;charset=UTF-8
        #
        #     grant_type=client_credentials
        #
        #
        #   The authorization server MUST authenticate the client.

        #XXX:Implement me!
        pass

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == "a":
            o = OAuthUserResource()
            d = o._renderAccessDialog(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == "a":
            o = OAuthUserResource()
            d = o._receiveUserAccess(request)
        elif segmentCount == 1 and request.postpath[0] == "t":
            request.setHeader("Access-Control-Allow-Origin","*")
            d = self._generateAccessToken(request)

        return self._epilogue(request, d)

class OAuthClientResource(base.BaseResource):
    isLeaf = True
    requireAuth = False
    _redirect_uri = config.get('General', 'URL') + "/client/cb"

    @defer.inlineCallbacks
    def _renderClient(self, request):
        #(appchange, script, args, myId) = yield self._getBasicArgs(request)
        #landing = not self._ajax
        cols = yield db.get_slice("xxx", "followers", count=1)

        args, landing = {"view":"client"}, True
        client_category = "code"
        client_id = utils.getRequestArg(request, 'id')
        if client_category == "code":
            response_type = "code"
        elif client_category == "client":
            response_type = "client_authentication"

        redirect_uri = self._redirect_uri
        scope = "feed"
        showpopup = utils.getRequestArg(request, 'view', sanitize=False)
        if showpopup:
            script = """
                    window.open( "/o/a?response_type=%s&client_id=%s&redirect_uri=%s&scope=%s",
                        "myWindow", "status = 1, height = 600, width = 600, resizable = 0")
                     """ %(response_type, client_id, redirect_uri, scope)
            request.write(script)
        else:
            args.update({"client_id":id})
            yield render(request, "oauth-client.mako", **args)


    @defer.inlineCallbacks
    def _renderCallback(self, request):
        # This dialog is rendered when the flockedin server calls the callback
        # with either a success auth code or error error code. Once the auth
        # code is received, third party client must POST the fIn server for
        # an access token using this auth code.

        #The authorization code generated by the
        # authorization server.  The authorization code MUST expire
        # shortly after it is issued to mitigate the risk of leaks.  A
        # maximum authorization code lifetime of 10 minutes is
        # RECOMMENDED.  The client MUST NOT use the authorization code
        # more than once.  If an authorization code is used more than
        # once, the authorization server MUST deny the request and SHOULD
        # attempt to revoke all tokens previously issued based on that
        # authorization code.  The authorization code is bound to the
        # client identifier and redirection URI.

        #(appchange, script, args, myId) = yield self._getBasicArgs(request)
        #landing = not self._ajax
        args, landing = {}, True
        code = utils.getRequestArg(request, 'code', sanitize=False)
        error_code = utils.getRequestArg(request, 'error_code', sanitize=False)

        yield render(request, "oauth-client.mako", **args)

        if code:
            args.update({"code":code, "redirect_url":self._redirect_uri})
            yield renderScriptBlock(request, "oauth-client.mako", "access_granted_layout",
                              landing, "#center", "set", **args)
        elif error_code:
            yield renderScriptBlock(request, "oauth-client.mako", "access_denied_layout",
                              landing, "#center", "set", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderClient(request)
        elif segmentCount == 1 and request.postpath[0] == "cb":
            d = self._renderCallback(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._actions(request)

        return self._epilogue(request, d)
