#!/usr/bin/python

import os
import sys
import optparse
import getpass
import uuid
import time
import pickle

from telephus.protocol import ManagedCassandraClientFactory
from telephus.client import CassandraClient
from telephus.cassandra.ttypes import ColumnPath, ColumnParent, Column, SuperColumn, KsDef, CfDef
from twisted.internet import defer, reactor
from twisted.python import log

sys.path.append(os.getcwd())
from social import config, db, utils, search


KEYSPACE = config.get("Cassandra", "Keyspace")
@defer.inlineCallbacks
def reindexProfileContent():
    rows = yield db.get_range_slice('entities', count=1000)
    for row in rows:
        entityId = row.key
        log.msg(entityId)
        entity = utils.supercolumnsToDict(row.columns)
        if entity.get('basic', {}).get('type', '') == 'user':
            orgId = entity['basic'].get('org', '')
            if orgId:
                yield search.solr.updatePeopleIndex(entityId, entity, orgId)




@defer.inlineCallbacks
def reindexItems():
    items = {}
    fetchedItems = yield db.get_range_slice('items', count=10000, reverse=True)
    for row in fetchedItems:
        items[row.key] = utils.supercolumnsToDict(row.columns)

    log.msg("Total items:", len(fetchedItems))
    for i, row in enumerate(fetchedItems):
        itemId = row.key
        item = items[itemId]
        log.msg(i+1, itemId)

        if 'meta' not in item or 'owner' not in item['meta']:
            continue

        owner = item['meta']['owner']
        try:
            col = yield db.get(owner, "entities", "org", "basic")
            ownerOrgId = col.column.value
        except:
            log.msg("Error when indexing:", itemId)
            continue

        parentId = item['meta'].get('parent', None)

        if not parentId:
            yield search.solr.updateItem(itemId, item, ownerOrgId)
        else:
            yield search.solr.updateItem(itemId, item, ownerOrgId, conv=items[parentId])


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-i', '--index-items', dest="items", action="store_true")
    parser.add_option('-p', '--index-people', dest='people', action="store_true")
    options, args = parser.parse_args()

    if options.items or options.people:
        log.startLogging(sys.stdout)
        db.startService()
        if options.items:
            d = reindexItems()
        if options.people:
            d = reindexProfileContent()


        def finish(x):
            db.stopService()
            reactor.stop();
        d.addErrback(log.err)
        d.addBoth(finish)
        reactor.run()
