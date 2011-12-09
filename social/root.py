
import urllib
import uuid
from email.utils            import formatdate

from zope.interface         import implements
from twisted.web            import resource, server, static, util, http
from twisted.internet       import defer
from twisted.python         import components

from social                 import db, utils, base, plugins
from social.logging         import log
from social.template        import render
from social.profile         import ProfileResource
from social.settings        import SettingsResource
from social.isocial         import IAuthInfo
from social.feed            import FeedResource
from social.signup          import SignupResource
from social.item            import ItemResource
from social.people          import PeopleResource
from social.avatar          import AvatarResource
from social.notifications   import NotificationsResource
from social.groups          import GroupsResource
from social.groups          import GroupFeedResource
from social.groups          import GroupSettingsResource
from social.fts             import FTSResource
from social.tags            import TagsResource
from social.auto            import AutoCompleteResource
from social.feedback        import FeedbackResource
from social.messaging       import MessagingResource
from social.admin           import Admin
from social.server          import SessionFactory
from social.files           import FilesResource
from social.embed           import EmbedResource
from social.contact         import ContactResource
from social.oauth           import OAuthResource
from social.api             import APIRoot
from social.apps            import ApplicationResource


def getPluggedResources(ajax=False):
    resources = {}
    for itemType in plugins:
        plugin = plugins[itemType]
        resource = plugin.getResource(ajax)
        if resource:
            resources[itemType] = resource

    return resources


#
# IAuthInfo: Interface with which data is stored the session.
#
class AuthInfo(components.Adapter):
    implements(IAuthInfo)
    def __init__(self, session):
        self.username = None
        self.organization = None
        self.isAdmin = False
        self.token = None

components.registerAdapter(AuthInfo, SessionFactory, IAuthInfo)


#
# SigninResource takes care of displaying the signin form and
# setting up the session for the user.
#
class SigninResource(resource.Resource):
    isLeaf = True

    AUTHENTICATION_FAILED = 'Username and password do not match'
    MISSING_FIELDS = 'Please enter both username and password'
    USER_BLOCKED = 'Account blocked or disabled'
    UNKNOWN_ERROR = 'Unknown Error. Please try again after sometime'

    @defer.inlineCallbacks
    def _saveSessionAndRedirect(self, request, data, remember=False):
        authinfo = yield defer.maybeDeferred(request.getSession,
                                             IAuthInfo, True, remember)
        authinfo.username = data["user"]
        authinfo.organization = data.get("org", None)
        authinfo.isAdmin = True if data.has_key("isAdmin") else False

        yield request._saveSessionToDB()
        redirectURL = utils.getRequestArg(request, "_r", sanitize=False) or "/feed"
        util.redirectTo(urllib.unquote(redirectURL), request)
        request.finish()

    @defer.inlineCallbacks
    def _renderSigninForm(self, request, errcode=''):
        args = {}
        redirect = utils.getRequestArg(request, '_r', sanitize=False) or "/feed"
        args["redirect"] = urllib.quote(redirect,  '*@+/')
        args["reason"] = errcode
        yield render(request, "signin.mako", **args)
        request.finish()

    def render_GET(self, request):
        d = defer.maybeDeferred(request.getSession, IAuthInfo)
        def checkSession(authinfo):
            if authinfo.username:
                redirectURL = utils.getRequestArg(request, "_r", sanitize=False) or "/feed"
                util.redirectTo(urllib.unquote(redirectURL), request)
                request.finish()
            else:
                self._renderSigninForm(request)
        d.addCallback(checkSession)
        return server.NOT_DONE_YET

    def render_POST(self, request):
        try:
            username = request.args['u'][0]
            password = request.args['p'][0]
            remember = request.args['r'][0] if 'r' in request.args else None
            if not username or not password:
                raise KeyError
        except KeyError:
            self._renderSigninForm(request, self.MISSING_FIELDS)
            return server.NOT_DONE_YET

        d = db.get_slice(username, "userAuth")
        def callback(result):
            cols = utils.columnsToDict(result)
            if not utils.checkpass(password, cols.get("passwordHash", "XXX")):
                return self._renderSigninForm(request, self.AUTHENTICATION_FAILED)
            if cols.has_key("isBlocked"):
                return self._renderSigninForm(request, self.USER_BLOCKED)
            self._saveSessionAndRedirect(request, cols, remember)
        def errback(error):
            return self._renderSigninForm(request, self.UNKNOWN_ERROR)
        d.addCallback(callback)
        d.addErrback(errback)

        return server.NOT_DONE_YET


#
# HomeResource gives an interface for the new users to signup
#
class HomeResource(resource.Resource):
    isLeaf = True

    def __init__(self):
        self.indexPage = static.File("public/index.html")

    def _renderHomePage(self, request):
        request.finish()

    def render_GET(self, request):
        d = defer.maybeDeferred(request.getSession, IAuthInfo)
        def checkSession(authinfo):
            if authinfo.username:
                util.redirectTo("/feed", request)
                request.finish()
            else:
                self.indexPage.render(request)
        d.addCallback(checkSession)
        return server.NOT_DONE_YET


#
# RootResource is responsible for setting up the url path structure, ensuring
# authorization, adding headers for cache busting and busting csrf.
#
class RootResource(resource.Resource):
    _noCSRFReset = set(["avatar", "auto", "rsrcs", "about", "signup", "signin", "password", "api"])

    def __init__(self, isAjax=False):
        self._isAjax = isAjax
        self._initResources()

    def _initResources(self):
        self._feed = FeedResource(self._isAjax)
        self._profile = ProfileResource(self._isAjax)
        self._settings = SettingsResource(self._isAjax)
        self._item = ItemResource(self._isAjax)
        self._tags = TagsResource(self._isAjax)
        self._people = PeopleResource(self._isAjax)
        self._notifications = NotificationsResource(self._isAjax)
        self._groups = GroupsResource(self._isAjax)
        self._groupFeed = GroupFeedResource(self._isAjax)
        self._groupSetting = GroupSettingsResource(self._isAjax)
        self._search = FTSResource(self._isAjax)
        self._admin = Admin(self._isAjax)
        self._pluginResources = getPluggedResources(self._isAjax)
        self._messages = MessagingResource(self._isAjax)
        self._files = FilesResource(self._isAjax)
        self._apps = ApplicationResource(self._isAjax)

        if not self._isAjax:
            self._home = HomeResource()
            self._ajax = RootResource(True)
            self._avatars = AvatarResource()
            self._auto = AutoCompleteResource()
            self._rsrcs = static.File("public/rsrcs")
            self._about = static.File("public/about")
            self._signup = SignupResource()
            self._signin = SigninResource()
            self._embed = EmbedResource()
            self._contact = ContactResource()
            self._oauth = OAuthResource()
            self._api = APIRoot()
        else:
            self._feedback = FeedbackResource(True)

    @defer.inlineCallbacks
    def _clearAuth(self, request):
        sessionId = request.getCookie(request.cookiename)
        if sessionId:
            yield request.site.clearSession(sessionId)

    @defer.inlineCallbacks
    def _ensureAuth(self, request, rsrc):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username != None:
            if request.method == "POST" or self._isAjax:
                token = utils.getRequestArg(request, "_tk")
                tokenFromCookie = request.getCookie('token')
                if token != tokenFromCookie:
                    defer.returnValue(resource.ErrorPage(400,
                            http.RESPONSES[400], "Invalid authorization token"))
            defer.returnValue(rsrc)
        elif self._isAjax:
            defer.returnValue(resource.ErrorPage(401, http.RESPONSES[401],
                              "You are not authorized to view this page"))
        else:
            signinPath = '/signin'
            if request.path != '/':
                signinPath = "/signin?_r=%s" % urllib.quote(request.uri, '*@+/')
            defer.returnValue(util.Redirect(signinPath))


    def getChildWithDefault(self, path, request):
        match = None

        # Resources that don't expose an AJAX interface
        if not self._isAjax:
            if path == "":
                match = self._home
            elif path == "auto":
                match = self._auto
            elif path == "ajax":
                match = self._ajax
            elif path == "embed":
                match = self._embed
            elif path == "signin":
                match = self._signin
            elif path == "avatar":
                match = self._avatars
            elif path == "about":
                match = self._about
            elif path == "contact":
                match = self._contact
            elif path == "signup":
                match = self._signup
            elif path == "rsrcs":
                match = self._rsrcs
            elif path == 'password':
                match = self._signup
            elif path == 'oauth':
                pathElement = request.postpath.pop(0)
                request.prepath.append(pathElement)
                match = self._oauth.getChildWithDefault(pathElement, request)

        # Resources that exist only on the AJAX interface
        elif path == "feedback":
            match = self._feedback

        # All other resources
        if path == "feed":
            match = self._feed
        elif path == "profile":
            match = self._profile
        elif path == "settings":
            match = self._settings
        elif path == "item":
            match = self._item
        elif path == "tags":
            match = self._tags
        elif path == "people":
            match = self._people
        elif path == "notifications":
            match = self._notifications
        elif path == "groups":
            match = self._groups
        elif path == 'group':
            match = self._groupFeed
        elif path == 'groupsettings':
            match = self._groupSetting
        elif path == "search":
            match = self._search
        elif path == "messages":
            match = self._messages
        elif path == "admin":
            match = self._admin
        elif path == "file":
            match = self._files
        elif path == "apps":
            match = self._apps
        elif path == "api":
            match = self._api

        # Resources exposed by plugins
        elif path in plugins and self._pluginResources.has_key(path):
            match = self._pluginResources[path]

        d = None
        if path == "signout":
            d = self._clearAuth(request)
            d.addCallback(lambda x: util.Redirect('/signin'))
        else:
            # We have no idea how to handle the given path!
            if not match:
                return resource.NoResource("Page not found")

            if not self._isAjax:
                # By default prevent caching.
                # Any resource may change these headers later during the processing
                request.setHeader('Expires', formatdate(0))
                request.setHeader('Cache-control', 'private,no-cache,no-store,must-revalidate')

            if self._isAjax or (not self._isAjax and match != self._ajax):
                if hasattr(match, 'requireAuth') and match.requireAuth:
                    d = self._ensureAuth(request, match)
                else:
                    d = defer.succeed(match)
            else:
                d = defer.succeed(match)

            #
            # We update the CSRF token when it is a GET request
            # and when one of the below is true
            #  - Ajax resource in which the full page is requested (appchange)
            #  - Non AJAX resource which is not in self._noCSRFReset
            #
            if ((self._isAjax and request.args.has_key('_fp')) or\
                        (not self._isAjax and match != self._ajax and\
                        path not in self._noCSRFReset))\
                        and request.method == "GET":
                def addTokenCallback(rsrc):
                    ad = defer.maybeDeferred(request.getSession, IAuthInfo)
                    @defer.inlineCallbacks
                    def gotAuthInfo(authinfo):
                        if authinfo.username:
                            token = str(uuid.uuid4())[:8]
                            request.addCookie('token', token, path='/')
                            authinfo.token = token
                            yield request._saveSessionToDB()
                        defer.returnValue(rsrc)
                    ad.addCallback(gotAuthInfo)
                    return ad
                d.addCallback(addTokenCallback)

        return util.DeferredResource(d)
