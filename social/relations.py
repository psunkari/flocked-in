from twisted.internet   import defer
from telephus.cassandra import ttypes

from social             import db, constants
from social.logging     import profile, dump_args, log

#
# Determine how the other person is related to me.
#
class Relation(object):
    def __init__(self, me, others):
        self.me = me
        self.others = others
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


    @defer.inlineCallbacks
    def initGroupsList(self):
        cols = yield db.get_slice(self.me, "entityGroupsMap")
        self.groups = [col.column.name.split(':', 1)[1] for col in cols]
