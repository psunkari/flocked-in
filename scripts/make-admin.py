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
from social import Config, Db, utils


KEYSPACE = Config.get("Cassandra", "Keyspace")


def usage():
    print("Usage: make-admin.py <email>")


@defer.inlineCallbacks
def makeAdmin(emailId):
    userAuth = yield Db.get_slice(emailId, "userAuth")
    if not userAuth:
        raise Exception('User does not exist')

    userAuth = utils.columnsToDict(userAuth)
    orgId = userAuth["org"]
    userId = userAuth["user"]
    yield Db.insert(orgId, "entities", "", userId, "admins")
    yield Db.insert(emailId, "userAuth", "True", "isAdmin")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage()
        sys.exit(2)

    log.startLogging(sys.stdout)
    d = makeAdmin(sys.argv[1])
    d.addErrback(log.err)
    d.addBoth(lambda x: reactor.stop())
    reactor.run()
