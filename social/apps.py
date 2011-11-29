
from base64             import b64encode
from ordereddict        import OrderedDict

from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _, fts
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
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

        if not all([name, redirect]):
            raise errors.MissingParams(["Name, Redirect URL"])

        knownScopes = globals().get('scopes')
        unknownScopes = [x for x in scope if x not in knownScopes.keys()]
        if category not in ["webapp", "native", "apikey"] or unknownScopes:
            raise errors.BaseError("Invalid value sent for Type/Permissions")

        clientId = utils.getUniqueKey()
        clientSecret = utils.getRandomKey()

        meta = {"author": myId, "name": name, "secret": clientSecret,
                "scope": ' '.join(scope), "category": category,
                "desc": desc, "redirect": b64encode(redirect)}
        yield db.batch_insert(clientId, "apps", {"meta":meta})
        yield db.insert(myId, "appsByOwner", "", clientId)
        yield db.insert(myOrgId, "appsByOwner", "", clientId)

        if script:
            request.write("$('#composer').empty();$$.fetchUri('/apps');")


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
            yield render(request, "apps.mako", **args)

        if script:
            self.setTitle(request, title)

        yield renderScriptBlock(request, "apps.mako",
                                "registrationForm", landing, "#apps-contents",
                                "set", **args)


    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        title = 'Applications'
        args['title'] = title
        args['detail'] = 'apps'

        if script and landing:
            yield render(request, "apps.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "apps.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            self.setTitle(request, title)

        clientId = utils.getRequestArg(request, 'id')

        if clientId:
            # XXX: Check no script case
            #      Fetch author information
            cols = yield db.get_slice(clientId, "apps")
            cols = utils.supercolumnsToDict(cols)
            if "meta" in cols:
                args.update(**cols["meta"])
                args.update({"id":clientId})
                yield renderScriptBlock(request, "apps.mako", "appDetails",
                                        landing, "#apps-contents", "set", **args)
            else:
                raise errors.InvalidEntity("application", clientId)
            return

        # XXX: Currently fetching all available apps under each category.
        #      In future implement pagination here.
        appIds = yield db.get_slice(myId, "entities", ["apikeys", "apps"], count=100)
        appIds = utils.supercolumnsToDict(appIds)

        appsByMe = yield db.get_slice(myId, "appsByOwner", count=100)
        appIds["my"] = utils.columnsToDict(appsByMe)

        toFetchClients = set()
        for val in appIds.values():
            toFetchClients.update(val.keys())

        clients = yield db.multiget_slice(toFetchClients, "apps")
        clients = utils.multiSuperColumnsToDict(clients)

        toFetchEntities = set([x.author for x in clients if 'author' in x])
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)

        args.update({'entities': entities, 'clients': clients, 'apps': appIds})
        if script:
            yield renderScriptBlock(request, "apps.mako", "appListing",
                                    landing, "#apps-contents", "set", **args)
        else:
            yield render(request, "apps.mako", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == "register":
            d = self._clientRegistrationForm(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == "register":
                d = self._registerClient(request)

        return self._epilogue(request, d)
