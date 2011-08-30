
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes

from social             import db, constants
from social.logging     import profile, dump_args

#
# Determine how the other person is related to me.
#
class Relation(object):
    def __init__(self, me, others):
        self.me = me
        self.others = others

        self.friends = {}           # friend Id => list of tags
        self.pending = {}           # user Ids => "0" (remote) or "1" (local)
        self.groups = []
        self.subscriptions = set()  # subscription Ids
        self.followers = set()       # follower Ids


    # Initialize self.following
    @profile
    @defer.inlineCallbacks
    @dump_args
    def initFollowersList(self):
        if self.others:
            cols = yield db.get_slice(self.me, "followers", self.others)
        else:
            cols = yield db.get_slice(self.me, "followers")

        self.followers = set([x.column.name for x in cols])


    # Initialize self.subscriptions
    @profile
    @defer.inlineCallbacks
    @dump_args
    def initSubscriptionsList(self):
        if self.others:
            cols = yield db.get_slice(self.me, "subscriptions", self.others)
        else:
            cols = yield db.get_slice(self.me, "subscriptions")

        self.subscriptions = set([x.column.name for x in cols])


    # Initialize self.friends, self.localPending and self.remotePending
    @profile
    @defer.inlineCallbacks
    @dump_args
    def initFriendsList(self):
        if self.others:
            cols = yield db.get_slice(self.me, 'connections', self.others)
        else:
            cols = yield db.get_slice(self.me, 'connections')

        self.friends = dict((x.super_column.name,\
                             [y.value for y in x.super_column.columns])\
                            for x in cols)


    # Initialize self.pending
    @profile
    @defer.inlineCallbacks
    @dump_args
    def initPendingList(self):
        if self.others:
            others = []
            for other in self.others:
                others.append('FI:%s'%(other))
                others.append('FO:%s'%(other))
            cols = yield db.get_slice(self.me, 'pendingConnections', others)
        else:
            cols = yield db.get_slice(self.me, 'pendingConnections')
        for col in cols:
            try:
                requestType, userId = col.column.name.split(':')
                self.pending[userId] = int(requestType == 'FI')
            except ValueError:
                pass

    @defer.inlineCallbacks
    def initGroupsList(self):
        cols = yield db.get_slice(self.me, "entityGroupsMap")
        self.groups = [col.column.name.split(':', 1)[1] for col in cols]
