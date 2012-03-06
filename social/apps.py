
from base64             import b64encode
from ordereddict        import OrderedDict

from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _
from social             import notifications, template as t
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args, log


scopes = OrderedDict([
    ('user-feed', 'Access your feed'),
    ('user-groups', 'Know which groups you are a member of'),
    ('user-subscriptions', 'Know which users and tags you are subscribed to'),
    ('user-followers', 'Know which users are following you'),
    ('user-profile', 'Access information on your profile'),
    ('user-notifications', 'Read your notifications'),
    ('user-messages', 'Read your private messages'),
    ('manage-profile', 'Manage your profile`'),
    ('manage-subscriptions', 'Manage your subscriptions'),
    ('manage-groups', 'Manage your groups'),
    ('manage-notifications', 'Manage your notifications'),
    ('post-item', 'Post items on your behalf'),
    ('send-message', 'Send private messages on your behalf'),
    ('org-groups', 'Access list of groups in your organization'),
    ('org-users', 'Access list of users in your organization'),
    ('other-profiles', 'Access profiles of other users')])


class ApplicationResource(base.BaseResource):
    isLeaf = True
    requireAuth = True
    _templates = ['apps.mako']


    def setTitle(self, request, title):
        if self._ajax:
            request.write('$("#apps-title").text("%s");' % title)
        else:
            request.write('<script>$("#apps-title").text("%s");</script>' % title)


    @defer.inlineCallbacks
    def _registerClient(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgId"]

        name = utils.getRequestArg(request, 'name')
        desc = utils.getRequestArg(request, 'desc')
        scope = utils.getRequestArg(request, 'scope', multiValued=True)
        category = utils.getRequestArg(request, 'category')
        redirect = utils.getRequestArg(request, 'redirect', sanitize=False)

        if not name:
            raise errors.MissingParams(["Name"])

        if not scope:
            raise errors.MissingParams(["Permissions"])

        if category != "apikey" and not redirect:
            raise errors.MissingParams(["Redirect URL"])

        knownScopes = globals().get('scopes')
        unknownScopes = [x for x in scope if x not in knownScopes.keys()]
        if category not in ["webapp", "native", "apikey"] or unknownScopes:
            raise errors.BaseError("Invalid value sent for Type/Permissions")

        clientId = utils.getUniqueKey()
        clientSecret = utils.getRandomKey()

        meta = {"author": myId, "name": name, "org": myOrgId,
                "secret": utils.hashpass(clientSecret),
                "scope": ' '.join(scope), "category": category}

        if category != "apikey":
            meta["redirect"] = b64encode(redirect)
            meta["desc"] = desc
            yield db.batch_insert(clientId, "apps", {"meta":meta})
            yield db.insert(myId, "appsByOwner", "", clientId)
            yield db.insert(myOrgId, "appsByOwner", "", clientId)
        else:
            yield db.batch_insert(clientId, "apps", {"meta":meta})
            yield db.insert(myId, "entities", "", clientId, "apikeys")

        self.setTitle(request, name)

        args['clientId'] = clientId
        args['client']  = meta
        args['client']['secret'] = clientSecret
        t.renderScriptBlock(request, "apps.mako", "registrationResults",
                            landing, "#apps-contents", "set", **args)


    @defer.inlineCallbacks
    def _clientRegistrationForm(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        args['detail'] = 'apps'

        apiKey = utils.getRequestArg(request, "type") == "apikey"
        title = 'Generate a new API Key' if apiKey\
                                         else 'Register a new application'
        args['apiKey'] = apiKey
        args['title'] = title

        if script and landing:
            t.render(request, "apps.mako", **args)

        if script:
            self.setTitle(request, title)

        t.renderScriptBlock(request, "apps.mako",
                            "registrationForm", landing, "#apps-contents",
                            "set", **args)


    @defer.inlineCallbacks
    def _renderClientDetails(self, request, clientId):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        args['detail'] = 'apps'

        if script and landing:
            t.render(request, "apps.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "apps.mako", "layout",
                                landing, "#mainbar", "set", **args)

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            raise errors.InvalidApp(clientId)

        args.update({'client': client, 'clientId': clientId})
        if script:
            self.setTitle(request, client['meta']['name'])

        author = base.Entity(client['meta']['author'])
        yield author.fetchData()
        args['entities'] = base.EntitySet(author)

        if script:
            t.renderScriptBlock(request, "apps.mako", "appDetails",
                                landing, "#apps-contents", "set", **args)
        else:
            t.render(request, "apps.mako", **args)


    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        title = 'Applications'
        args['title'] = title
        args['detail'] = 'apps'

        if script and landing:
            t.render(request, "apps.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "apps.mako", "layout",
                                landing, "#mainbar", "set", **args)

        if script:
            self.setTitle(request, title)

        # XXX: Currently fetching all available apps under each category.
        #      In future implement pagination here.
        appIds = yield db.get_slice(myId, "entities", ["apikeys", "apps"], count=100)
        appIds = utils.supercolumnsToDict(appIds, timestamps=True)

        appsByMe = yield db.get_slice(myId, "appsByOwner", count=100)
        appIds["my"] = utils.columnsToDict(appsByMe)

        toFetchClients = set()
        for val in appIds.values():
            toFetchClients.update(val.keys())

        clients = yield db.multiget_slice(toFetchClients, "apps")
        clients = utils.multiSuperColumnsToDict(clients)

        toFetchEntities = set([x.author for x in clients if 'author' in x])
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()

        args.update({'entities': entities, 'clients': clients, 'apps': appIds})
        if script:
            t.renderScriptBlock(request, "apps.mako", "appListing",
                                landing, "#apps-contents", "set", **args)
        else:
            t.render(request, "apps.mako", **args)


    # XXX: Confirm deletion of the application
    @defer.inlineCallbacks
    def _delete(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        clientId = utils.getRequestArg(request, "id", sanitize=False)

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            raise errors.InvalidApp(clientId)

        if client['meta']['author'] != myId:
            raise errors.AppAccessDenied(clientId)

        yield db.remove(clientId, "apps")
        yield db.remove(myId, "appsByOwner", clientId)
        yield db.remove(myOrgId, "appsByOwner", clientId)


    @defer.inlineCallbacks
    def _revoke(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        clientId = utils.getRequestArg(request, "id", sanitize=False)

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            raise errors.InvalidApp(clientId)

        me = yield db.get_slice(myId, "entities", ["apikeys", "apps"])
        me = utils.supercolumnsToDict(me)

        # Remove the client in case of API Key
        if client['meta']['category'] == 'apikey':
            if client['meta']['author'] != myId:
                raise errors.AppAccessDenied(clientId)

            d1 = db.remove(clientId, "apps")
            d2 = db.remove(myId, "appsByOwner", clientId)
            d3 = db.remove(myId, "entities", clientId, "apikeys")
            d4 = db.remove(myOrgId, "appsByOwner", clientId)
            yield defer.DeferredList([d1, d2, d3, d4])

        # Remove the refresh token
        # XXX: Valid access tokens could still exist
        else:
            authorization = me['apps'][clientId]
            d1 = db.remove(myId, "entities", clientId, "apps")
            d2 = db.remove(authorization, "oAuthData")
            yield defer.DeferredList([d1, d2])


    # XXX: Confirm generation of new secret
    @defer.inlineCallbacks
    def _secret(self, request):
        myId = request.getSession(IAuthInfo).username
        clientId = utils.getRequestArg(request, "id", sanitize=False)

        client = yield db.get_slice(clientId, "apps")
        client = utils.supercolumnsToDict(client)
        if not client:
            raise errors.InvalidApp(clientId)

        if client['meta']['author'] != myId:
            raise errors.AppAccessDenied(clientId)

        clientSecret = utils.getRandomKey()
        yield db.insert(clientId, "apps", utils.hashpass(clientSecret),
                        "secret", "meta")

        args = {'clientId': clientId, 'client': client['meta'],
                'info': 'New application secret was generated'}
        args['client']['secret'] = clientSecret
        t.renderScriptBlock(request, "apps.mako", "registrationResults",
                            False, "#apps-contents", "set", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            clientId = utils.getRequestArg(request, 'id')
            if clientId:
                d = self._renderClientDetails(request, clientId)
            else:
                d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == "register":
            d = self._clientRegistrationForm(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1:
            action = request.postpath[0]
            if action == "register":
                d = self._registerClient(request)
            elif action == "delete":
                d = self._delete(request)
            elif action == "revoke":
                d = self._revoke(request)
            elif action == "secret":
                d = self._secret(request)

        return self._epilogue(request, d)

