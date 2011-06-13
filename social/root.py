
import urllib
from email.utils            import formatdate

from zope.interface         import implements
from twisted.web            import resource, server, static, util, http
from twisted.internet       import defer
from twisted.python         import log, components

from social                 import Db, utils, base, plugins
from social.template        import render
from social.profile         import ProfileResource
from social.isocial         import IAuthInfo
from social.feed            import FeedResource
from social.signup          import SignupResource
from social.item            import ItemResource
from social.people          import PeopleResource
from social.avatar          import AvatarResource
from social.notifications   import NotificationsResource
from social.groups          import GroupsResource
from social.fts             import FTSResource
from social.tags            import TagsResource
from social.auto            import AutoCompleteResource
from social.feedback        import FeedbackResource
from social.messaging       import MessagingResource
from social.admin           import Admin
from social.server          import SessionFactory


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
    def _saveSessionAndRedirect(self, request, data):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo, True)
        authinfo.username = data["user"]
        authinfo.organization = data.get("org", None)
        authinfo.isAdmin = True if data.has_key("isAdmin") else False

        redirectURL = utils.getRequestArg(request, "_r") or "/feed"
        util.redirectTo(urllib.unquote(redirectURL), request)
        request.finish()

    @defer.inlineCallbacks
    def _renderSigninForm(self, request, errcode=''):
        args = {}
        redirect = utils.getRequestArg(request, '_r') or "/feed"
        args["redirect"] = urllib.quote(redirect,  '*@+/')
        args["reason"] = errcode
        yield render(request, "signin.mako", **args)
        request.finish()

    def render_GET(self, request):
        d = defer.maybeDeferred(request.getSession, IAuthInfo)
        def checkSession(authinfo):
            if authinfo.username:
                redirectURL = utils.getRequestArg(request, "_r") or "/feed"
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
            if not username or not password:
                raise KeyError
        except KeyError:
            self._renderSigninForm(request, self.MISSING_FIELDS)
            return server.NOT_DONE_YET

        d = Db.get_slice(username, "userAuth")
        def callback(result):
            cols = utils.columnsToDict(result)
            if cols.get("passwordHash", "XXX") != utils.md5(password):
                return self._renderSigninForm(request, self.AUTHENTICATION_FAILED)
            if cols.has_key("isBlocked"):
                return self._renderSigninForm(request, self.USER_BLOCKED)
            self._saveSessionAndRedirect(request, cols)
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
        self.indexPage = static.File("private/index.html")

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
# authorization, adding headers for cache busting and setting some default cookies
#
class RootResource(resource.Resource):
    _noCookiesPaths = set(["avatar", "auto", "signin", "signup", "public", "about"])

    def __init__(self, isAjax=False):
        self._isAjax = isAjax
        self._initResources()

    def _initResources(self):
        self._feed = FeedResource(self._isAjax)
        self._profile = ProfileResource(self._isAjax)
        self._item = ItemResource(self._isAjax)
        self._tags = TagsResource(self._isAjax)
        self._people = PeopleResource(self._isAjax)
        self._notifications = NotificationsResource(self._isAjax)
        self._groups = GroupsResource(self._isAjax)
        self._search = FTSResource(self._isAjax)
        self._admin = Admin(self._isAjax)
        self._pluginResources = getPluggedResources(self._isAjax)
        self._feedback = FeedbackResource(self._isAjax)
        self._messages = MessagingResource(self._isAjax)
        if not self._isAjax:
            self._home = HomeResource()
            self._ajax = RootResource(True)
            self._avatars = AvatarResource()
            self._auto = AutoCompleteResource()
            self._public = static.File("public")
            self._about = static.File("about")
            self._signup = SignupResource()
            self._signin = SigninResource()

    def _clearAuth(self, request):
        sessionId = request.getCookie(request.cookiename)
        if sessionId:
            request.site.clearSession(sessionId)

    @defer.inlineCallbacks
    def _ensureAuth(self, request, rsrc):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username != None:
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
        if not self._isAjax:
            if path == "":
                match = self._home
            elif path == "auto":
                match = self._auto
            elif path == "ajax":
                match = self._ajax
            elif path == "signin":
                match = self._signin
            elif path == "avatar":
                match = self._avatars
            elif path == "about":
                match = self._about
            elif path == "signup":
                match = self._signup
            elif path == "public":
                match = self._public
            elif path == "signout":
                self._clearAuth(request)
                match = util.Redirect('/signin')

        if path == "feed":
            match = self._feed
        elif path == "profile":
            match = self._profile
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
        elif path == "search":
            match = self._search
        elif path == "messages":
            match = self._messages
        elif path == "admin":
            match = self._admin
        elif path == "feedback":
            match = self._feedback
        elif path in plugins and self._pluginResources.has_key(path):
            match = self._pluginResources[path]

        # We have no idea how to handle the given path!
        if not match:
            return resource.NoResource("Page not found")

        # By default prevent caching.
        # Any resource may change these headers later during the processing
        if not self._isAjax:
            request.setHeader('Expires', formatdate(0))
            request.setHeader('Cache-control', 'private,no-cache,no-store,must-revalidate')

        if self._isAjax or (not self._isAjax and match != self._ajax):
            if hasattr(match, 'requireAuth') and match.requireAuth:
                d = self._ensureAuth(request, match)
            else:
                d = defer.succeed(match)

            if request.method == "GET" and path not in self._noCookiesPaths\
                                and (not self._isAjax or "_fp" in request.args):
                def addPageIndicatorCookie(rsrc, request, path):
                    request.addCookie("page", path, path="/")
                    return rsrc
                d.addCallback(addPageIndicatorCookie, request, path)
        else:
            d = defer.succeed(match)

        return util.DeferredResource(d)
