
from urllib                     import quote_plus, unquote_plus

from zope.interface             import Interface, Attribute, implements
from twisted.cred.portal        import IRealm, Portal
from twisted.cred.credentials   import ICredentials
from twisted.cred.error         import Unauthorized, LoginFailed
from twisted.web                import resource, util, http, server, static
from twisted.internet           import defer, threads, reactor
from twisted.python             import log, components

from social                     import Config, Db, utils
from social.template            import render
from social.isocial             import IAuthInfo

#
# IAuthInfo: Interface with which data is stored the session.
#            This is temporary and will actually move to memcached
#
class AuthInfo(components.Adapter):
    implements(IAuthInfo)
    def __init__(self, session):
        self.username = None

components.registerAdapter(AuthInfo, server.Session, IAuthInfo)


# Shortcut util to get username from the session.
def getMyKey(request):
    authinfo = request.getSession(IAuthInfo)
    return authinfo.username


#
# SigninForm: We are responsible for displaying the signin form
#
class SigninForm(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        args = {"query": ""};
        if request.args.has_key("_r"):
            args["query"] = "?_r=" + request.args["_r"][0]

        d = render(request, "signin.mako", **args)
        d.addCallback(lambda x: request.finish())
        return server.NOT_DONE_YET


class AuthRealm(object):
    implements(IRealm)
    def __init__(self, root):
        self.root = root

    def requestAvatar(self, (username, redirectURL), request, *interfaces):
        if redirectURL is not None:
            return util.Redirect(redirectURL)
        else:
            return self.root


#
# UserPasswordChecker: Connect to LDAP to check if the password are right.
# We add the username and password to the session so that they can be used
# when authenticating to other services.
#
# Since we anyway connect to LDAP, fetch the list of services that this user
# has access to - which will be part of the avatar that should technically be
# retrieved by the realm. But that's okay, lets optimize a little.
#
class IUserPassword(ICredentials):
    username = Attribute("Username of the connecting user")
    password = Attribute("Password of the user")
    request  = Attribute("Connection's request object")


class UserPassword(object):
    implements(IUserPassword)
    def __init__(self, username, password, request):
        self.username = username
        self.password = utils.md5(password)
        self.request  = request

class UserPasswordChecker():
    credentialInterfaces = [IUserPassword]

    def _authenticate(self, username, password):
        d = Db.get_slice(username, "userAuth",
                         ["passwordHash", "org", "user", "isAdmin", "isBlocked"])
        def checkPassword(result):
            cols = utils.columnsToDict(result)
            if not cols.has_key("passwordHash") or\
                   cols["passwordHash"] != password:
                raise LoginFailed()
            if "isBlocked" in cols and cols["isBlocked"] == "True":
                raise  Unauthorized()
            return cols

        def erred(error):
            log.err(error)
            raise Unauthorized()
        d.addCallbacks(checkPassword, erred)
        return d

    def requestAvatarId(self, cred):
        d = self._authenticate(cred.username, cred.password)
        def setCookie(auth):
            session = cred.request.getSession()
            session.sessionTimeout = 14400  # Timeout of 4 hours
            authinfo = session.getComponent(IAuthInfo)
            authinfo.username = auth["user"]
            authinfo.organization = auth["org"] if auth.has_key("org") else None
            authinfo.isAdmin = auth["isAdmin"] if auth.has_key("isAdmin") else False
            return authinfo.username
        d.addCallback(setCookie)

        def addRedirectURL(username):
            redirectURL = "/"
            if cred.request.args.has_key("_r"):
                redirectURL = unquote_plus(cred.request.args["_r"][0])
            return (username, redirectURL)
        d.addCallback(addRedirectURL)

        return d


#
# SessionChecker: Validate the session. We only check to make sure that we
# have a valid session which includes a username and password
#
class IUserSession(ICredentials):
    request = Attribute("Connection's request object")


class UserSession(object):
    implements(IUserSession)
    def __init__(self, request):
        self.request = request


class UserSessionChecker():
    credentialInterfaces = [IUserSession]

    def signout(self, cred):
        session = cred.request.getSession()
        session.unsetComponent(IAuthInfo)

    def requestAvatarId(self, cred):
        authInfo = cred.request.getSession(IAuthInfo)
        if authInfo.username is None:
            # Don't ask for login when in DevMode.
            if Config.get('General', 'DevMode') == 'True':
                authInfo.username = Config.get('General', 'DevModeUsername')
                return (authInfo.username, None)

            # We don't have session and we are not in DevMode.
            else:
                return defer.fail(Unauthorized())

        if cred.request.postpath[0] == "signout":
            self.signout(cred)
            return (None, "/signin")

        return (authInfo.username, None)



#
# AuthTokenChecker: See if there is a token attached with the request.
# Access tokens make it possible for the system to give access to a few
# features without requiring the users to signin (or to share with users
# that don't have an account on our server)
#
class IAuthToken(ICredentials):
    token = Attribute("The authentication token")
    request = Attribute("Connection's request object")


class AuthToken(object):
    implements(IAuthToken)
    def __init__(self, token, request):
        self.token = token
        self.request = request


class AuthTokenChecker():
    credentialInterfaces = [IAuthToken]

    def requestAvatarId(self, credentials):
        log.msg("TODO: Authtoken Handler")
        return defer.fail(Unauthorized())



#
# AuthWrapper: Wrap the original site and add authentication to it. Obviously
# it should take care of letting the user signin by visiting /signin
#
class AuthWrapper(object):
    implements(resource.IResource)
    isLeaf = False
    def __init__(self, portal):
        self.portal = portal
        self.public = static.File("public")

    def render(self, request):
        return self._authorized(request).render(request)

    def getChildWithDefault(self, name, request):
        if request.method == "GET":
            # Allow access to the signin form
            if name == "signin":
                return SigninForm()

            if name == "register":
                #inline import because of 'cyclic imports'.
                #reorder the import to prevent cyclic imports
                from social.register import RegisterResource
                return RegisterResource()

            # Allow access to public/static files.
            # On production systems this should be handled by dedicated
            # static file servers - nginX maybe.
            elif name == "public":
                return self.public

        if request.method == "POST":
            if name == "register":
                from social.register import RegisterResource
                return RegisterResource()

        request.postpath.insert(0, request.prepath.pop())
        return self._authorized(request)

    def _authorized(self, request):
        credentials = None

        # First, check if the user is trying to signin.
        if request.postpath[0] == "signin" and request.method == "POST":
            try:
                username = request.args['u'][0]
                password = request.args['p'][0]
                if username == "" or password == "":
                    raise KeyError
            except KeyError:    # XXX: Find better way to manage errors
                return util.Redirect("/signin?_e=MissingFields")
            else:
                credentials = UserPassword(username, password, request)

        # Second, check if this request includes an authtoken
        elif request.args.has_key("_token"):
            credentials = AuthToken(request.args["_token"], request)

        # Lastly, look if we already have authinfo in the session
        else:
            credentials = UserSession(request)

        d = self.portal.login(credentials, request)

        def errorDuringSignin(failure):
            failure = failure.trap(LoginFailed, Unauthorized)
            if request.path[0:5] == "/ajax" and issubclass(failure, Unauthorized):
                return resource.ErrorPage(401, http.RESPONSES[401], "You are not authorized to view this page")
            elif request.path == "/signout":
                return util.Redirect("/signin")

            afterLogin = None
            errorCode = None

            rUrl = "/signin"
            if request.path == "/signin":
                afterLogin = utils.getRequestArg(request, "_r")
            elif request.path != "/":
                afterLogin = request.uri

            if issubclass(failure, LoginFailed):
                errorCode = "InvalidCredentials"

            if afterLogin and errorCode:
                rUrl = rUrl + "?_r=%s&_e=%s" % (afterLogin, errorCode)
            elif afterLogin:
                rUrl = rUrl + "?_r=%s" % (afterLogin)
            elif errorCode:
                rUrl = rUrl + "?_e=%s" % (errorCode)

            return util.Redirect(rUrl)
        d.addErrback(errorDuringSignin)

        return util.DeferredResource(d)
