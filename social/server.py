
import cPickle as pickle
import time
from email.utils            import formatdate

from twisted.web            import resource, server, static, util
from twisted.internet       import defer
from twisted.python         import log, components

from social                 import db, utils, base, plugins
from social.isocial         import IAuthInfo


class RequestFactory(server.Request):
    cookiename = 'session'
    session = None
    session_saved = False

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
                               expires=formatdate(time.time()+31536000))
            else:           # Cookie expires at the end of browser session
                self.addCookie(self.cookiename, self.session.uid, path='/')
            return _component()
        d.addCallbacks(callback)
        d.addErrback(errback)
        return d


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
        serialized = pickle.dumps(session)
        yield db.insert(uid, "sessions", serialized, "auth", ttl=self.timeout)

    @defer.inlineCallbacks
    def clearSession(self, uid):
        yield db.remove(uid, "sessions", "auth")
