
import json
try:
    import cPickle as pickle
except:
    import pickle
from operator               import itemgetter

from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils, comet
from social.base            import BaseResource
from social.isocial         import IAuthInfo
from social.logging         import log

class PresenceStates:
    OFFLINE   = 'offline'
    X_AWAY    = 'x-away'
    AWAY      = 'away'
    BUSY      = 'busy'
    AVAILABLE = 'available'
    ORDERED   = [OFFLINE, X_AWAY, AWAY, BUSY, AVAILABLE]

def getMostAvailablePresence(states):
    mostAvailable = 0
    for state in states:
        idx = PresenceStates.ORDERED.index(state)
        if idx > mostAvailable:
            mostAvailable = idx
    return PresenceStates.ORDERED[mostAvailable]

class PresenceResource(BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _updatePresence(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        orgId = authinfo.organization
        sessionId = request.getCookie('session')

        status = utils.getRequestArg(request, 'status', sanitize=None)
        if status not in PresenceStates.ORDERED:
            raise request.InvalidRequest('Unknown status identifier')

        # Check if there is a change in the online status
        results = yield db.getSlice(orgId, 'presence', super_column=myId)
        results = utils.columnsToDict(results)
        mostAvailablePresence = getMostAvailablePresence(results.values())

        # Update the online status
        yield db.insert(orgId, 'presence', status, sessionId, myId)

        # If status changed broadcast the change
        # XXX: Currently everyone on the network will get the presence update.
        #      This will not scale well with big networks
        if mostAvailablePresence != status:
            me = yield db.get_slice(myId, "entities", ['basic'])
            me = utils.supercolumnsToDict(me)
            data = {"userId": myId, 'status': status,
                    'name': me['basic']['name'],
                    'avatar': utils.userAvatar(myId, me, 's')}
            yield comet.push('/presence/'+orgId, data)
        if status == PresenceStates.OFFLINE:
            yield private.ClearChannels(myId, sessionId)


    @defer.inlineCallbacks
    def _getPresence(self, request):
        authInfo = request.getSession(IAuthInfo)
        orgId = authInfo.organization
        myId = authInfo.username
        sessionId = request.getCookie('session')

        status = utils.getRequestArg(request, 'status', sanitize=None)
        log.info(status, status in PresenceStates.ORDERED, PresenceStates.ORDERED)
        if status not in PresenceStates.ORDERED:
            raise request.InvalidRequest('Unknown status identifier')


        cols = yield db.get_slice(orgId, "presence",)
        cols = utils.supercolumnsToDict(cols)
        if myId not in cols:
            myPresence = yield db.get_slice(orgId, "presence", super_column=myId)
            cols[myId] = utils.columnsToDict(myPresence)
        presence = {}
        for userId in cols:
            presence[userId] = getMostAvailablePresence(cols[userId].values())

        userIds = cols.keys()
        cols = yield db.multiget_slice(userIds, "entities", ['name', 'avatar'], super_column='basic')
        entities = utils.multiColumnsToDict(cols)
        data = []
        for entityId in entities:
            entity = entities[entityId]
            entities[entityId]['status'] = presence.get(userId, PresenceStates.OFFLINE)
            _data = {"userId": entityId, "name": entity['name'],
                     "status": presence.get(userId, PresenceStates.OFFLINE),
                     "avatar": utils.userAvatar(entityId, entity, 's')}
            if entityId == myId and status != presence[myId]:
                _data['status'] = status
                yield comet.push('/presence/'+orgId, _data)
            data.append(_data)
        yield db.insert(orgId, 'presence', status, sessionId, myId)
        request.write(json.dumps(data))


    def render_POST(self, request):
        segmentCount = len(request.postpath)

        if segmentCount == 1 and request.postpath[0] == "":
            d = self._updatePresence(request)

        return self._epilogue(request, d)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        print request.postpath

        if segmentCount == 1 and request.postpath[0] == "" or segmentCount ==0:
            d = self._getPresence(request)

        return self._epilogue(request, d)
