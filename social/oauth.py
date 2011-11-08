import uuid
from base64     import urlsafe_b64encode, urlsafe_b64decode
import hmac
import hashlib

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



class OAuthResource(base.BaseResource):
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
        scope = utils.getRequestArg(request, 'scope', multiValued=True)

        #If the request fails due to a missing, invalid, or mismatching
        # redirection URI, or if the client identifier provided is invalid, the
        # authorization server SHOULD inform the resource owner of the error,
        # and MUST NOT automatically redirect the user-agent to the invalid
        # redirection URI.

        if not all([response_type, client_id, redirect_uri, scope]):
            raise errors.MissingParams([])

        args.update({"view":"fIn"})
        if script and landing:
            yield render(request, "oauth-server.mako", **args)

        #TODO:Sanitize and verify client_id
        if client_id :
            cols = yield db.get_slice(client_id, "oAuthClients")
            cols = utils.supercolumnsToDict(cols)
            args.update(**cols["meta"])
            args.update({"client_id":client_id})
            args.update({"redirect_uri":redirect_uri})
            signature_message = "%s:%s:%s" %(client_id, myId, urlsafe_b64encode(redirect_uri))
            digest_maker = hmac.new(myOrgId, signature_message, hashlib.sha256)
            signature = digest_maker.hexdigest()
            args.update({"signature":signature})
            yield renderScriptBlock(request, "oauth-server.mako",
                                    "access_layout",
                                    landing, "#center", "set", **args)

            if appchange and script:
                yield renderScriptBlock(request, "oauth-server.mako",
                                        "access_layout", landing, "#center",
                                        "set", **args)

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

        # Check if signature is valid and whether client_id + user id +
        # redirect url match
        signature = utils.getRequestArg(request, 'signature')
        signature_message = "%s:%s:%s" %(client_id, myId, urlsafe_b64encode(redirect_uri))
        digest_maker = hmac.new(myOrgId, signature_message, hashlib.sha256)
        recieved_signature = digest_maker.hexdigest()

        if signature != recieved_signature:
            raise errors.PermissionDenied("Signature Does not match")

        cols = yield db.get_slice(client_id, "oAuthClients")
        cols = utils.supercolumnsToDict(cols)
        client_redirects = cols['meta']['client_redirects'].split(":")

        if allow_access == "true":
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
            auth_code = utils.getRandomKey(myId)
            if urlsafe_b64encode(redirect_uri) in client_redirects:
                yield db.insert(auth_code, "oAuthorizationCodes", myId,
                                client_id, ttl=600)
                yield db.insert(myId, "oAuthCodes2User", client_id, auth_code)
                Location = redirect_uri + "?code=%s" %auth_code
            else:
                raise errors.PermissionDenied("Redirect URI does not match")
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
            if urlsafe_b64encode(redirect_uri) in client_redirects:
                Location = redirect_uri + "?error_code=%s" %error
            else:
                raise errors.PermissionDenied("Redirect URI does not match")

        else:
            raise errors.MissingParams([])

        request.write("window.location.href = '%s'" %Location)

    def _generateAccessToken(self, request):
        pass

    @defer.inlineCallbacks
    def _registerClient(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        #Enforce the scope that is set during the registration of an app at all
         #times. Later a preference by the user can be set that will limit all
         # future scopes by an app for this user to that list.
        #The authorization server MAY fully or partially ignore the scope
        #requested by the client based on the authorization server policy or
        #the resource owner's instructions.  If the issued access token scope
        #is different from the one requested by the client, the authorization
        #server SHOULD include the "scope" response parameter to inform the
        #client of the actual scope granted.

        client_name = utils.getRequestArg(request, 'client_name')
        client_category = utils.getRequestArg(request, 'client_category')
        client_scope = utils.getRequestArg(request, 'client_scope',
                                           multiValued=True)
        client_id = utils.getRandomKey(myId)
        client_redirects = utils.getRequestArg(request, 'client_redirect_url',
                                               sanitize=False, multiValued=True)
        client_desc = utils.getRequestArg(request, 'client_desc')

        # 1. An auth code, access token is always mapped to the
        # a. User who requested it.
        # b. The app(app id) whom this user had invoked.
        # XXX:c. The redirection_url that was mentioned in the request.
        # 2. An auth code is revoked when it is used more than once.
        # The access token is mapped to the auth code. So if an auth code
        # is revoked(not expired), all access tokens need to be discarded.
        # 3. Make sure only one access token is issued against the above
        #  combination at all times. If a new auth code or access token is
        # requested, make sure to discard all previous ones wrt 1.a ~ 1.c .
        if not all([client_name, client_category, client_scope, client_redirects]):
            raise errors.MissingParams(["Name or Redirect URLs"])

        client_redirects = [urlsafe_b64encode(x) for x in client_redirects]

        if client_category == "client":
            client_password = utils.getUniqueKey()
        else:
            client_password = ""

        client_meta = {
                        "client_author":myId,
                        "client_name":client_name,
                        "client_password":client_password,
                        "client_scope":":".join(list(client_scope)),
                        "client_category":client_category,
                        "client_redirects":":".join(list(client_redirects)),
                        "client_desc":client_desc
                     }
        print "%s:%s:%s:%s:%s:%s" %(client_name, client_category, client_scope,
                                 client_id, client_password,client_redirects)
        yield db.batch_insert(client_id, "oAuthClients", {"meta":client_meta})
        yield db.insert(myId, "oUser2Clients", client_name, client_id)

        if script:
            request.write("$('#composer').empty();$$.fetchUri('/o/clients');")

    @defer.inlineCallbacks
    def _renderClientRegistrationDialog(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "oauth-server.mako", **args)

        yield renderScriptBlock(request, "oauth-server.mako",
                                "registration_layout", landing, "#composer",
                                "set", **args)

    @defer.inlineCallbacks
    def _renderClientDetailsDialog(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "oauth-server.mako", **args)

        client_id = utils.getRequestArg(request, 'id')
        if client_id:
            cols = yield db.get_slice(client_id, "oAuthClients")
            cols = utils.supercolumnsToDict(cols)
            args.update(**cols["meta"])
            args.update({"client_id":client_id})
            yield renderScriptBlock(request, "oauth-server.mako",
                                    "application_details_layout",
                                    landing, "#center", "set", **args)
        else:
            start = utils.getRequestArg(request, "start") or ''
            cols = yield db.get_slice(myId, "oUser2Clients", count=10,
                                      start=start)
            client_ids = [col.column.name for col in cols]
            cols = yield db.multiget_slice(client_ids, 'oAuthClients', ['meta'])
            client_details = utils.multiSuperColumnsToDict(cols)
            print client_details
            args.update({"apps":client_details})
            yield renderScriptBlock(request, "oauth-server.mako",
                                    "application_listing_layout",
                                    landing, "#center", "set", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            pass
        elif segmentCount == 1 and request.postpath[0] == "a":
            d = self._renderAccessDialog(request)
        elif segmentCount == 1 and request.postpath[0] == "clients":
            d = self._renderClientDetailsDialog(request)
        elif segmentCount == 1 and request.postpath[0] == "new":
            d = self._renderClientRegistrationDialog(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._actions(request)
        elif segmentCount == 1 and request.postpath[0] == "a":
            d = self._receiveUserAccess(request)
        elif segmentCount == 1 and request.postpath[0] == "t":
            d = self._generateAccessToken(request)
        elif segmentCount == 1 and request.postpath[0] == "clients":
            d = self._registerClient(request)

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
                        "myWindow", "status = 1, height = 300, width = 500, resizable = 0")
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
            args.update({"code":code})
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
