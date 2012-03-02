
import json
try:
    import cPickle as pickle
except:
    import pickle

from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils, errors, presence
from social.base            import APIBaseResource
from social.isocial         import IAuthInfo


class PrivateResource(APIBaseResource):
    requireAuth = False
    isLeaf = True

    @defer.inlineCallbacks
    def _validateSession(self, request):
        sessionId = utils.getRequestArg(request, "sessionid", sanitize=False)
        if not sessionId:
            raise errors.NotFoundError()

        try:
            session = yield defer.maybeDeferred(request.site.getSession, sessionId)
            session = session.getComponent(IAuthInfo)
            self._success(request, 200, {'user': session.username,
                                         'org': session.organization})
        except ttypes.NotFoundException:
            raise errors.NotFoundError()

    @defer.inlineCallbacks
    def disconnect(self, request):
        sessionId = utils.getRequestArg(request, "sessionid", sanitize=False)
        try:
            session = yield defer.maybeDeferred(request.site.getSession, sessionId)
        except ttypes.NotFoundException:
            raise errors.NotFoundError()

        userId = session.getComponent(IAuthInfo).username
        orgId = session.getComponent(IAuthInfo).organization
        yield utils.cleanupChat(sessionId, userId, orgId)
        self._success(request, 200, {})

    @defer.inlineCallbacks
    def isAuthorized(self, request):
        sessionId = utils.getRequestArg(request, "sessionid", sanitize=False)
        channelId = utils.getRequestArg(request, "channelid", sanitize=False)

        if not sessionId or not channelId:
            raise errors.NotFoundError()

        try:
            session = yield defer.maybeDeferred(request.site.getSession, sessionId)
        except ttypes.NotFoundException:
            raise errors.NotFoundError()
        userId = session.getComponent(IAuthInfo).username
        if len(channelId.split('/chat/')) != 2:
            raise errors.InvalidRequest()
        nullString, channelId = channelId.split('/chat/')

        channels = yield db.get_slice(channelId, "channelSubscribers")
        channels = utils.columnsToDict(channels)
        if not channels:
            self._success(request, 404, {"reason": "Channel not found"})
        elif userId not in channels:
            self._success(request, 401, {"reason": "Not authorized"})
        else:
            self._success(request, 200, {"reason": "OK"})

    def render_GET(self, request):
        d = None
        segmentCount = len(request.postpath)

        if segmentCount == 1 and request.postpath[0] == "validate-session":
            d = self._validateSession(request)
        elif segmentCount == 1 and request.postpath[0] == "disconnect":
            d = self.disconnect(request)
        elif segmentCount == 1 and request.postpath[0] == "is-authorized":
            d = self.isAuthorized(request)
        return self._epilogue(request, d)
