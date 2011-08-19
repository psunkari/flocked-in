#!/usr/bin/python

import os
import sys

from twisted.internet import defer, reactor
from twisted.python import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")

@defer.inlineCallbacks
def recreateEntityGroupMap():
    """
        change the column names of entityGroupsMap to new format
        GroupName:GroupId
    """
    rows = yield db.get_range_slice('entityGroupsMap',
                                    count=10000,
                                    reverse=True)
    entity_map = {}
    groupIds = []
    for row in rows:
        entityId = row.key
        cols = utils.columnsToDict(row.columns)
        if entityId not in entity_map:
            entity_map[entityId]  = []
        entity_map[entityId].extend(cols.keys())
        groupIds.extend(cols.keys())
    cols = yield db.multiget_slice(set(groupIds), "entities", ["basic"])
    cols = utils.multiSuperColumnsToDict(cols)
    for entityId in entity_map:
        for groupId in entity_map[entityId]:
            yield db.remove(entityId, "entityGroupsMap", groupId)
            if groupId in cols:
                name = cols[groupId]["basic"]["name"].replace(':', '')
                colname = "%s:%s" % (name, groupId)
                yield db.insert(entityId, "entityGroupsMap", "", colname)


if __name__ == '__main__':
    log.startLogging(sys.stdout)
    db.startService()
    d = recreateEntityGroupMap()

    def finish(x):
        db.stopService()
        reactor.stop()
    d.addErrback(log.err)
    d.addBoth(finish)

    reactor.run()
