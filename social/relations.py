
from social import Db


RELATION_SELF       = 0x01
RELATION_FRIEND     = 0x02
RELATION_EXTENDED   = 0x04
RELATION_GROUP      = 0x08
RELATION_DOMAIN     = 0x10
RELATION_MANAGER    = 0x20
RELATION_REPORTS    = 0x40


def getUserRelation(one, two):
    if one == two:
        return UserRelation(RELATION_SELF)


class UserRelation(object):
    type = 0x0
    groups = []
    tags = []
    friends = []

    def __init__(self, type):
        self.type = type
