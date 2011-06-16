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
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


def usage():
    print("Usage: make-admin.py <email>")


@defer.inlineCallbacks
def makeAdmin(emailId):
    userAuth = yield db.get_slice(emailId, "userAuth")
    if not userAuth:
        raise Exception('User does not exist')

    userAuth = utils.columnsToDict(userAuth)
    orgId = userAuth["org"]
    userId = userAuth["user"]
    yield db.insert(orgId, "entities", "", userId, "admins")
    yield db.insert(emailId, "userAuth", "True", "isAdmin")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage()
        sys.exit(2)

    log.startLogging(sys.stdout)
    db.startService()
    d = makeAdmin(sys.argv[1])

    def finish(x):
        db.stopService()
        reactor.stop();
    d.addErrback(log.err)
    d.addBoth(finish)

    reactor.run()
