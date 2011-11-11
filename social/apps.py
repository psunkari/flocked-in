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


class ApplicationResource(base.BaseResource):
    isLeaf = True
    requireAuth = True


    @defer.inlineCallbacks
    def _registerClient(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        #Enforce the scope that is set during the registration of an app at all
         #times. User must be allowed to modify the scope of an app.
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
        # c. The redirection_url that was mentioned in the request.
        # XXX2. An auth code is revoked when it is used more than once.
        # The access token is mapped to the auth code. So if an auth code
        # is revoked(not expired), all access tokens need to be discarded.
        if not all([client_name, client_category, client_scope, client_redirects]):
            raise errors.MissingParams(["Name or Redirect URLs"])

        client_redirects = [urlsafe_b64encode(x) for x in client_redirects]

        if client_category == "client":
            client_password = utils.getUniqueKey()
        else:
            client_password = ""

        #Assign weights to scope. 1 for read, 2 for modify. So feed will get 1
        # if dev registers for read only or 3 if for full access
        scope_weights = {"feed":0, "profile": 0, "people":0}
        if "feed_w" in client_scope:
            scope_weights["feed"] = 3
        elif "feed" in client_scope:
            scope_weights["feed"] = 1

        if "profile_w" in client_scope:
            scope_weights["profile"] = 3
        elif "profile" in client_scope:
            scope_weights["profile"] = 1

        if "people_w" in client_scope:
            scope_weights["people"] = 3
        elif "people" in client_scope:
            scope_weights["people"] = 1

        client_scope = pickle.dumps(scope_weights)

        client_meta = {
                        "client_author":myId,
                        "client_name":client_name,
                        "client_password":client_password,
                        "client_scope":client_scope,
                        "client_category":client_category,
                        "client_redirects":":".join(list(client_redirects)),
                        "client_desc":client_desc
                     }
        print "%s:%s:%s:%s:%s:%s" %(client_name, client_category, client_scope,
                                 client_id, client_password,client_redirects)
        yield db.batch_insert(client_id, "oAuthClients", {"meta":client_meta})
        yield db.insert(myId, "oUser2Clients", client_name, client_id)

        if script:
            request.write("$('#composer').empty();$$.fetchUri('/apps');")

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

        if appchange and script:
            yield renderScriptBlock(request, "oauth-server.mako", "layout",
                              landing, "#mainbar", "set", **args)

        client_id = utils.getRequestArg(request, 'id')
        if client_id:
            cols = yield db.get_slice(client_id, "oAuthClients")
            cols = utils.supercolumnsToDict(cols)
            if "meta" in cols:
                args.update(**cols["meta"])
                args.update({"client_id":client_id})
                yield renderScriptBlock(request, "oauth-server.mako",
                                        "application_details_layout",
                                        landing, "#center", "set", **args)
            else:
                raise errors.InvalidEntity("Application", client_id)
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
            d = self._renderClientDetailsDialog(request)
        elif segmentCount == 1 and request.postpath[0] == "new":
            d = self._renderClientRegistrationDialog(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._registerClient(request)

        return self._epilogue(request, d)
