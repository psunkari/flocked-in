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
from social import config, db, utils, fts


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
                yield fts.solr.updatePeopleIndex(entityId, entity, orgId)




@defer.inlineCallbacks
def reindexItems():
    """
        re index all items
    """
    rows = yield db.get_range_slice('items', count=10000, reverse=True)
    data = {}
    i=0
    log.msg("no.of items", len(rows))
    for row in rows:
        i +=1
        itemId = row.key
        log.msg(itemId, i)
        item = utils.supercolumnsToDict(row.columns)
        if 'meta' not in item:
            continue
        if 'owner' not in item['meta']:
            continue
        owner = item['meta']['owner']
        try:
            col = yield db.get(owner, "entities", "org", "basic")
            ownerOrgId = col.column.value
        except:
            log.msg(itemId, "error")
            continue

        if item['meta'].get('type', '') == 'poll':
            item['meta']['poll_options'] = ' '.join(item['options'].values())
        yield fts.solr.updateIndex(itemId, item, ownerOrgId)



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
