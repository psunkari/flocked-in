
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
    ('user-groups', 'List of your groups'),
    ('user-subscriptions', 'List of your subscriptions'),
    ('user-followers', 'List of your followers'),
    ('user-profile', 'Information on your profile'),
    ('user-notifications', 'Your notifications'),
    ('user-messages', 'Your private messages'),
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

        clientId = utils.getUniqueKey()
        password = utils.getRandomKey()

        meta = {"author": myId, "name": name, "password": password,
                "scope": ','.join(scope), "category": category,
                "desc": desc, "redirect": b64encode(redirect)}
        yield db.batch_insert(clientId, "apps", {"meta":meta})
        yield db.insert(myId, "appsByOwner", "", clientId)
        yield db.insert(myOrgId, "appsByOwner", "", clientId)

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

        clientId = utils.getRequestArg(request, 'id')
        if clientId:
            cols = yield db.get_slice(clientId, "apps")
            cols = utils.supercolumnsToDict(cols)
            if "meta" in cols:
                args.update(**cols["meta"])
                args.update({"id":clientId})
                yield renderScriptBlock(request, "oauth-server.mako",
                                        "application_details_layout",
                                        landing, "#center", "set", **args)
            else:
                raise errors.InvalidEntity("Application", clientId)
        else:
            start = utils.getRequestArg(request, "start") or ''
            cols = yield db.get_slice(myId, "appsByOwner", count=10, start=start)
            clientIds = [col.column.name for col in cols]
            cols = yield db.multiget_slice(clientIds, 'apps', ['meta'])
            details = utils.multiSuperColumnsToDict(cols)
            args.update({"apps":details})
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
