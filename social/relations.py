
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes

from social import Db, utils

# Relation between two users - mainly used for authentication
REL_UNRELATED       = 0x000
REL_SELF            = 0x001
REL_FRIEND          = 0x002
REL_EXTENDED        = 0x004
REL_GROUP           = 0x008
REL_DOMAIN          = 0x100
REL_MANAGER         = 0x200
REL_REPORTS         = 0x400
REL_TEAM            = 0x800
REL_LOCAL_PENDING   = 0x100
REL_REMOTE_PENDING  = 0x200
REL_FOLLOWER        = 0x400

#
# Determine how I am related to the other person.
# The results are all in the perspective of the other person and are primarily
# meant to be used by the authorization engine.
#
# Eg: For connections, remote pending really means that it is pending with me
#     Tags indicate how 'other' tagged me.
#
# However, many things here give hints that can be used when rendering pages.
# Eg: Render an "Add as friend" button if both are not connected.
#
class Relation(object):
    def __init__(self, me, other):
        self.me = me
        self.other = other

        self._fetchedFriendInfo = False
        self.isFriend = REL_UNRELATED
        self.isFriendTags = []

        self._fetchedFollowingInfo = False
        self.isFollower = REL_UNRELATED


    def isMe(self):
        return True if self.me == self.other else False

    # Return REL_FOLLOWER if I am following the other user or REL_UNRELATED
    @defer.inlineCallbacks
    def checkIsFollowing(self):
        if not self._fetchedFollowingInfo:
            try:
                if not self.isMe():
                    result = yield Db.get(self.other, 'followers', self.me)
                    self.isFollower = REL_FOLLOWER
            except ttypes.NotFoundException:
                self.isFollower = REL_UNRELATED
            finally:
                self._fetchedFollowingInfo = True

        defer.returnValue(self.isFollower)

    # Return REL_FRIEND, REL_REMOTE_PENDING, REL_LOCAL_PENDING or REL_UNRELATED
    @defer.inlineCallbacks
    def checkIsFriend(self, tag=None):
        if not self._fetchedFriendInfo:
            try:
                if not self.isMe():
                    result = yield Db.get(self.other, 'connections', None, self.me)
                    cols = utils.supercolumnsToDict([result])

                    if cols[self.me].has_key("__local__"):
                        self.isFriend = REL_LOCAL_PENDING
                    elif cols[self.me].has_key("__remote__"):
                        self.isFriend = REL_REMOTE_PENDING
                    else:
                        self.isFriend = REL_FRIEND
                        self.isFriendTags = cols[self.me].keys()
            except ttypes.NotFoundException:
                self.isFriend = REL_UNRELATED
            finally:
                self._fetchedFriendInfo = True

        if not tag:
            defer.returnValue(self.isFriend)
        else:
            retVal = REL_FRIEND if tag in self.isFriendTags else REL_UNRELATED
            defer.returnValue(retVal)

    # Return REL_GROUP or REL_UNRELATED
    def haveCommonGroup(self, group=None):
        pass

    # Return REL_DOMAIN or REL_UNRELATED
    def haveSameDomain(self):
        pass

    # Return REL_MANAGER, REL_REPORT, REL_TEAM or REL_UNRELATED
    def isOrgRelated(self, type=REL_TEAM):
        pass
