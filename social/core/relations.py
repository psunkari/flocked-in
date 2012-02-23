from twisted.internet   import defer
from telephus.cassandra import ttypes

from social             import db, constants

#
# Determine how the other person is related to me.
#
class Relations(object):
    def __init__(self, myId, others):
        self.myId = myId
        self.others = others
        self.groups = []
        self.subscriptions = set()   # subscription Ids
        self.followers = set()       # follower Ids


    # Initialize self.following
    @defer.inlineCallbacks
    def initFollowersList(self):
        if self.others:
            cols = yield db.get_slice(self.myId, "followers", self.others)
        else:
            cols = yield db.get_slice(self.myId, "followers")
        self.followers = set([x.column.name for x in cols])


    # Initialize self.subscriptions
    @defer.inlineCallbacks
    def initSubscriptionsList(self):
        if self.others:
            cols = yield db.get_slice(self.myId, "subscriptions", self.others)
        else:
            cols = yield db.get_slice(self.myId, "subscriptions")
        self.subscriptions = set([x.column.name for x in cols])


    @defer.inlineCallbacks
    def initGroupsList(self):
        cols = yield db.get_slice(self.myId, "entityGroupsMap")
        self.groups = [col.column.name.split(':', 1)[1] for col in cols]
