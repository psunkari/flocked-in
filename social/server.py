
import cPickle as pickle

from twisted.web            import resource, server, static, util
from twisted.internet       import defer
from twisted.python         import log, components

from social                 import Db, utils, base, plugins


class RequestFactory(server.Request):
    cookiename = 'auth'
    session = None

    def getSession(self, sessionInterface=None, create=False):
        def _component():
            if sessionInterface:
                return self.session.getComponent(sessionInterface)
            else:
                return self.session

        # We already have the session and createNew is False
        if self.session and not create:
            return _component()

        # Save the updated session (only if we have a valid authinfo)
        def requestDone(ignored):
            self.site.updateSession(self.session.uid, self.session)
        self.notifyFinish().addCallback(requestDone)

        # If we have a session cookie, try to fetch the session from Db
        # We use the existing session-id only if create is False
        sessionId = self.getCookie(self.cookiename) if not create else None
        d = self.site.getSession(sessionId) if sessionId else defer.fail([])
        def callback(session):
            self.session = session
            return _component()
        def errback(failure):
            self.session = self.site.makeSession()
            self.addCookie(self.cookiename, self.session.uid, path='/')
            return _component()
        d.addCallbacks(callback, errback)
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
        result = yield Db.get(uid, "sessions", "data")
        serialized = result.column.value
        defer.returnValue(pickle.loads(serialized))

    @defer.inlineCallbacks
    def updateSession(self, uid, session):
        serialized = pickle.dumps(session)
        yield Db.insert(uid, "sessions", serialized, "data", ttl=self.timeout)

    @defer.inlineCallbacks
    def clearSession(self, uid):
        yield Db.remove(uid, "sessions", "data")
