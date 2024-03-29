
import json
try:
    import cPickle as pickle
except:
    import pickle
from operator               import itemgetter

from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils,  errors, base
from social.isocial         import IAuthInfo
from social.logging         import log
from social                 import template as t
from social.comet           import comet


class PresenceStates:
    AWAY = 'away'
    BUSY = 'busy'
    X_AWAY = 'x-away'
    OFFLINE = 'offline'
    AVAILABLE = 'available'
    ORDERED = [OFFLINE, X_AWAY, AWAY, BUSY, AVAILABLE]


@defer.inlineCallbacks
def clearChannels(userId, sessionId):
    key = "%s:%s" % (userId, sessionId)
    cols = yield db.get_slice(key, "sessionChannelsMap")
    channels = utils.columnsToDict(cols).keys()
    for channelId in channels:
        yield db.remove(channelId, "channelSubscribers", key)
    yield db.remove(key, "sessionChannelsMap")


@defer.inlineCallbacks
def updateAndPublishStatus(userId, orgId, sessionId, status, user=None):
    # Check if there is a change in the online status
    results = yield db.get_slice(orgId, 'presence', super_column=userId)
    results = utils.columnsToDict(results)
    oldPublishedStatus = getMostAvailablePresence(results.values())

    # Update the online status
    if status != 'offline':
        yield db.insert(orgId, 'presence', status, sessionId, userId)
    else:
        yield db.remove(orgId, 'presence', sessionId, userId)

    # If status changed broadcast the change
    # XXX: Currently everyone on the network will get the presence update.
    #      This will not scale well with big networks
    results[sessionId] = status
    newPublishedStatus = getMostAvailablePresence(results.values())

    if oldPublishedStatus != newPublishedStatus:
        if not user:
            user = base.Entity(userId)
            yield user.fetchData()
        data = {"userId": userId, 'status': newPublishedStatus,
                'name': user.basic['name'],
                'title': user.basic['jobTitle'],
                'avatar': utils.userAvatar(userId, user, 's')}
        yield comet.publish('/presence/' + orgId, data)


def getMostAvailablePresence(states):
    mostAvailable = 0
    for state in states:
        idx = PresenceStates.ORDERED.index(state)
        if idx > mostAvailable:
            mostAvailable = idx
    return PresenceStates.ORDERED[mostAvailable]


class PresenceResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _updatePresence(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        orgId = authinfo.organization
        sessionId = request.getCookie('session')

        status = utils.getRequestArg(request, 'status', sanitize=None)
        if status not in PresenceStates.ORDERED:
            raise errors.InvalidRequest('Unknown status identifier')

        yield updateAndPublishStatus(myId, orgId, sessionId, status)
        if status == PresenceStates.OFFLINE:
            yield clearChannels(myId, sessionId)

    @defer.inlineCallbacks
    def _getPresence(self, request):
        authInfo = request.getSession(IAuthInfo)
        orgId = authInfo.organization
        myId = authInfo.username
        data = []

        cols = yield db.get_slice(orgId, "presence")
        cols = utils.supercolumnsToDict(cols)
        if myId not in cols:
            myPresence = yield db.get_slice(orgId, "presence", super_column=myId)
            cols[myId] = utils.columnsToDict(myPresence)

        presence = {}
        for userId in cols:
            presence[userId] = getMostAvailablePresence(cols[userId].values())

        if presence[myId] == PresenceStates.OFFLINE:
            request.write(json.dumps(data))
            return

        userIds = cols.keys()
        entities = base.EntitySet(userIds)
        yield entities.fetchData()
        for entityId in entities.keys():
            entity = entities[entityId]
            _data = {"userId": entityId, "name": entity.basic['name'],
                     "status": presence.get(entityId, PresenceStates.OFFLINE),
                     "title": entity.basic["jobTitle"],
                     "avatar": utils.userAvatar(entityId,  entity, 's')}
            data.append(_data)

        request.write(json.dumps(data))

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._updatePresence(request)

        return self._epilogue(request, d)

    def render_GET(self, request):
        segmentCount = len(request.postpath)

        d = None
        if segmentCount == 0:
            d = self._getPresence(request)

        return self._epilogue(request, d)
