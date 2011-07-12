#!/usr/bin/python

import os
import sys
import getopt
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
def createIndex():
    """
        re index all items
    """
    rows = yield db.get_range_slice('items', count=10000, reverse=True)
    data = {}
    for row in rows:
        itemId = row.key
        item = utils.supercolumnsToDict(row.columns)
        itemType = item['meta'].get('type', '')
        if item['meta'].get('type', '') == 'poll':
            item['meta']['options_str'] = ' '.join(item['options'].values())
        yield fts.solr.updateIndex(itemId, item)



if __name__ == '__main__':
    log.startLogging(sys.stdout)
    db.startService()
    d = createIndex()

    def finish(x):
        db.stopService()
        reactor.stop();
    d.addErrback(log.err)
    d.addBoth(finish)

    reactor.run()
