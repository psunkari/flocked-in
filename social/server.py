
import cPickle as pickle
import time
from email.utils            import formatdate

from twisted.web            import resource, server, static, util
from twisted.internet       import defer
from twisted.python         import components

from social                 import db, utils, base, plugins, config
from social.isocial         import IAuthInfo
from social.logging         import log

secureCookies = False
try:
    secureCookies = config.get("General", "SSLOnlyCookies")
except: pass
COOKIE_DOMAIN = config.get('General', "CookieDomain")

class RequestFactory(server.Request):
    cookiename = 'session'
    session = None
    session_saved = False
    apiAccessToken = None

    @defer.inlineCallbacks
    def _saveSessionToDB(self, ignored=None):
        if self.session and not self.session_saved and\
           self.session.getComponent(IAuthInfo).username:
            yield self.site.updateSession(self.session.uid, self.session)
            self.session_saved = True

    def getSession(self, sessionInterface=None, create=False, remember=False):
        def _component():
            if sessionInterface:
                return self.session.getComponent(sessionInterface)
            else:
                return self.session

        # We already have the session and createNew is False
        if self.session and not create:
            return _component()

        # Save the updated session (only if we have a valid authinfo)
        self.notifyFinish().addErrback(self._saveSessionToDB)

        # If we have a session cookie, try to fetch the session from db
        # We use the existing session-id only if create is False
        sessionId = self.getCookie(self.cookiename)
        if sessionId and create:
            self.site.clearSession(sessionId)

        sessionId = sessionId if not create else None
        d = self.site.getSession(sessionId) if sessionId else defer.fail([])
        def callback(session):
            self.session = session
            return _component()
        def errback(failure):
            self.session = self.site.makeSession()
            if remember:    # Cookie expires in 1 year
                self.addCookie(self.cookiename, self.session.uid, path='/',
                               expires=formatdate(time.time()+31536000),
                               secure=secureCookies, domain=COOKIE_DOMAIN, http_only=True)
            else:           # Cookie expires at the end of browser session
                self.addCookie(self.cookiename, self.session.uid, path='/',
                               secure=secureCookies, domain=COOKIE_DOMAIN, http_only=True)
            return _component()
        d.addCallbacks(callback)
        d.addErrback(errback)
        return d

    # Copy of code from twisted.web.http
    # Adds support for httpOnly flag in cookie
    def addCookie(self, k, v, expires=None, domain=None, path=None,
                  max_age=None, comment=None, secure=None, http_only=None):
        """
        Set an outgoing HTTP cookie.

        In general, you should consider using sessions instead of cookies, see
        L{twisted.web.server.Request.getSession} and the
        L{twisted.web.server.Session} class for details.
        """
        cookie = '%s=%s' % (k, v)
        if expires is not None:
            cookie = cookie +"; Expires=%s" % expires
        if domain is not None:
            cookie = cookie +"; Domain=%s" % domain
        if path is not None:
            cookie = cookie +"; Path=%s" % path
        if max_age is not None:
            cookie = cookie +"; Max-Age=%s" % max_age
        if comment is not None:
            cookie = cookie +"; Comment=%s" % comment
        if secure:
            cookie = cookie +"; Secure"
        if http_only:
            cookie = cookie +"; HttpOnly"
        self.cookies.append(cookie)


class SessionFactory(components.Componentized):
    def __init__(self, uid):
        components.Componentized.__init__(self)
        self.uid = uid


class SiteFactory(server.Site):
    timeout = 604800

    def makeSession(self):
        uid = self._mkuid()
        session = self.sessionFactory(uid)
        return session

    @defer.inlineCallbacks
    def getSession(self, uid):
        result = yield db.get(uid, "sessions", "auth")
        serialized = result.column.value
        defer.returnValue(pickle.loads(serialized))

    @defer.inlineCallbacks
    def updateSession(self, uid, session):
        userId = session.getComponent(IAuthInfo).username
        serialized = pickle.dumps(session)
        yield db.insert(uid, "sessions", serialized, "auth", ttl=self.timeout)
        yield db.insert(userId, "userSessionsMap", '', uid, ttl=self.timeout)

    @defer.inlineCallbacks
    def clearSession(self, uid):
        session = yield self.getSession(uid)
        authInfo = session.getComponent(IAuthInfo)
        userId = authInfo.username
        orgId = authInfo.organization
        yield db.remove(uid, "sessions", "auth")
        yield db.remove(userId, "userSessionsMap", uid)
        yield db.remove(orgId, "presence", uid, userId)
        yield utils.cleanupChat(uid, userId, orgId)
