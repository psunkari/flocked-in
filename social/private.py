
import json
try:
    import cPickle as pickle
except:
    import pickle

from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils, errors
from social.base            import APIBaseResource
from social.isocial         import IAuthInfo

@defer.inlineCallbacks
def clearChannels(userId, sessionId):

    key = "%s:%s"%(userId, sessionId)
    cols = yield db.get_slice(key, "sessionChannelsMap")
    channels = utils.columnsToDict(cols).keys()
    for channelId in channels:
        yield db.remove(channelId, "channelSubscribers", key)
    yield db.remove(key, "sessionChannelsMap")

class PrivateResource(APIBaseResource):
    requireAuth = False
    isLeaf = True

    @defer.inlineCallbacks
    def disconnect(self, request):
        sessionId = utils.getRequestArg(request, "id", sanitize=False)
        userId = utils.getRequestArg(request, "userId")
        yield clearChannels(userId, sessionId)
        self._success(request, 200)

    @defer.inlineCallbacks
    def isAuthorised(self, request):
        channelId = utils.getRequestArg(request, "id", sanitize=False)
        userId = utils.getRequestArg(request, "userId")
        try:
            yield db.get(channelId, "channelSubscribers")
        except ttypes.NotFoundException:
           self._success(request, 404)
        try:
            yield db.get(channelId, "channelSubscribers", userId)
            self._success(request, 200)
        except ttypes.NotFoundException:
           self._success(request, 401)






    @defer.inlineCallbacks
    def _validateSession(self, request):
        sessionId = utils.getRequestArg(request, "id", sanitize=False)
        if not sessionId:
            raise errors.NotFoundError()

        try:
            session = yield defer.maybeDeferred(request.site.getSession, sessionId)
            session = session.getComponent(IAuthInfo)
            self._success(request, 200, {'user':session.username,
                                         'org':session.organization})
        except ttypes.NotFoundException:
            raise errors.NotFoundError()


    def render_GET(self, request):
        d = None
        segmentCount = len(request.postpath)

        if segmentCount == 1 and request.postpath[0] == "validate-session":
            d = self._validateSession(request)
        elif segmentCount == 1 and request.postpath[0] == "disconnect":
            d = self.disconnect(request)
        elif segmentCount ==1 and request.postpath[0] == "is-authorised":
            d = self.isAuthorised(request)
        return self._epilogue(request, d)
