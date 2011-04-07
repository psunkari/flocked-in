
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes

from social import Db, utils, constants

#
# Determine how the other person is related to me.
#
class Relation(object):
    def __init__(self, me, others):
        self.me = me
        self.others = others

        self.friends = {}           # friend Id => list of tags
        self.pending = {}           # user Ids => "0" (remote) or "1" (local)
        self.subscriptions = None   # subscription Ids
        self.followers = None       # follower Ids


    # Initialize self.following
    @defer.inlineCallbacks
    def initFollowersList(self):
        if self.others:
            cols = yield Db.get_slice(self.me, "followers", self.others)
        else:
            cols = yield Db.get_slice(self.me, "followers")

        self.followers = set([x.column.name for x in cols])


    # Initialize self.subscriptions
    @defer.inlineCallbacks
    def initSubscriptionsList(self):
        if self.others:
            cols = yield Db.get_slice(self.me, "subscriptions", self.others)
        else:
            cols = yield Db.get_slice(self.me, "subscriptions")

        self.subscriptions = set([x.column.name for x in cols])


    # Initialize self.friends, self.localPending and self.remotePending
    @defer.inlineCallbacks
    def initFriendsList(self):
        if self.others:
            cols = yield Db.get_slice(self.me, 'connections', self.others)
        else:
            cols = yield Db.get_slice(self.me, 'connections')

        self.friends = dict((x.super_column.name,\
                             [y.value for y in x.super_column.columns])\
                            for x in cols)


    # Initialize self.pending
    @defer.inlineCallbacks
    def initPendingList(self):
        if self.others:
            cols = yield Db.get_slice(self.me, 'pendingConnections', self.others)
        else:
            cols = yield Db.get_slice(self.me, 'pendingConnections')
        self.pending = dict((x.column.name, x.column.value) for x in cols)
