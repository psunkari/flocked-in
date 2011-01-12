
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes

from social import Db

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
        self._isFriend = REL_UNRELATED
        self._isFriendTags = []

    def isMe(self):
        return True if self.me == self.other else False

    # Return REL_FRIEND, REL_REMOTE_PENDING, REL_LOCAL_PENDING or REL_UNRELATED
    @defer.inlineCallbacks
    def isFriend(self, tag=None):
        if not self._fetchedFriendInfo:
            try:
                if not self.isMe():
                    result = yield Db.get(self.other, 'connections', self.me)
                    tags = result.column.value
                    if tags == "__local__":
                        self._isFriend = REL_LOCAL_PENDING
                    elif tags == "__remote__":
                        self._isFriend = REL_REMOTE_PENDING
                    else:
                        self._isFriend = REL_FRIEND
                        self._isFriendTags = tags.split(',')
            except ttypes.NotFoundException:
                self._isFriend = REL_UNRELATED
            finally:
                self._fetchedFriendInfo = True

        if not tag:
            defer.returnValue(self._isFriend)
        else:
            retVal = REL_FRIEND if tag in self._isFriendTags else REL_UNRELATED
            defer.returnValue(retVal)

    # Return REL_EXTENDED or REL_UNRELATED
    def isExtendedFriend(self, tag=None):
        pass

    # Return REL_GROUP or REL_UNRELATED
    def haveCommonGroup(self, group=None):
        pass

    # Return REL_DOMAIN or REL_UNRELATED
    def haveSameDomain(self):
        pass

    # Return REL_MANAGER, REL_REPORT, REL_TEAM or REL_UNRELATED
    def isOrgRelated(self, type=REL_TEAM):
        pass
