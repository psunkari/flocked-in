#!/usr/bin/python

import os
import sys
import time

from telephus.protocol import ManagedCassandraClientFactory
from telephus.client import CassandraClient
from telephus.cassandra.ttypes import ColumnPath, ColumnParent, Column, SuperColumn, KsDef, CfDef, Deletion, SlicePredicate
from twisted.internet import defer, reactor
from twisted.python import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


@defer.inlineCallbacks
def migrateFriendsToFollowers():
    # Migrate all friends to followers/subscriptions.
    connectionRows = yield db.get_range_slice('connections', count=10000)
    for connectionRow in connectionRows:
        userId = connectionRow.key
        friends = [x.super_column.name for x in connectionRow.columns]
        yield db.batch_insert(userId, "followers", dict([(x, '') for x in friends]))
        yield db.batch_mutate(dict([(x, {'subscriptions': {userId: ''}}) for x in friends]))
    log.msg('>>>>>>>> Converted all connections to following.')

    # Remove name indices of friends
    entityRows = yield db.get_range_slice('entities', count=10000, names=['basic'])
    entities = dict([(x.key, utils.supercolumnsToDict(x.columns)) for x in entityRows])
    userIds = [x for x in entities.keys() if entities[x]['basic']['type'] == 'user']
    for userId in userIds:
        yield db.remove(userId, 'displayNameIndex')
        yield db.remove(userId, 'nameIndex')
    log.msg('>>>>>>>> Removed name indices for friends.')

    # Convert all "connection" activity to "follow".
    # We already have two separate items, so subtype conversion should be good.
    itemRows = yield db.get_range_slice('items', count=10000, names=['meta'])
    items = dict([(x.key, utils.supercolumnsToDict(x.columns)) for x in itemRows])
    connectionItems = [x for x in items.keys()\
                       if items[x]['meta'].get('type', '') == 'activity'\
                          and items[x]['meta']['subType'] == 'connection']
    yield db.batch_mutate(dict([(x, {'items':{'meta':{'subType':'following'}}}) for x in connectionItems]))
    log.msg('>>>>>>>> All connection items converted to following.')

    # Remove all friend requests from pendingConnections
    pendingRows = yield db.get_range_slice('pendingConnections', count=10000)
    for pendingRow in pendingRows:
        userId = pendingRow.key
        pendingFriendRequestIds = [x.column.name for x in pendingRow.columns \
                                   if not x.column.name.startswith('G')]
        if pendingFriendRequestIds:
            yield db.batch_remove({'pendingConnections': [userId]}, names=pendingFriendRequestIds)
    log.msg('>>>>>>>> Removed pending friend requests.')

    # Remove all friend requests from latest
    yield db.batch_remove({'latest': userIds}, names='people')
    log.msg('>>>>>>>> Removed friend requests from latest.')

    # Remove all friend-request-accepted notifications
    notifyMutations = {}
    for userId in userIds:
        items = yield db.get_slice(userId, "notificationItems", super_column=':FA')
        if items:
            names = [col.column.name for col in items]
            colmap = dict([(x, None) for x in names])
            deletion = Deletion(time.time() * 1000000, 'notifications',
                                SlicePredicate(column_names=names))
            notifyMutations[userId] = {'notifications': colmap, 'latest': [deletion]}
            yield db.remove(userId, 'notificationItems', super_column=':FA')
    if notifyMutations:
        yield db.batch_mutate(notifyMutations)
    log.msg('>>>>>>>> Removed friend notifications from notifications and latest.')

    # Finally, remove the connections column family.
    yield db.system_drop_column_family('connections')
    yield db.system_drop_column_family('connectionsByTag')
    log.msg('>>>>>>>> Removed the connections column family.')


if __name__ == '__main__':
    log.startLogging(sys.stdout)
    db.startService()
    d = migrateFriendsToFollowers()

    def finish(x):
        db.stopService()
        reactor.stop();
    d.addErrback(log.err)
    d.addBoth(finish)

    reactor.run()
