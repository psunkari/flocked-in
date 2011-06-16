#!/usr/bin/python

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
    print("Usage: create-user.py -e<email> -n<name> -t<title> -z<timezone>")


@defer.inlineCallbacks
def getOrgKey(domain):
    cols = yield Db.get_slice(domain, "domainOrgMap")
    cols = utils.columnsToDict(cols)
    orgKey = cols.keys()[0] if cols else None
    defer.returnValue(orgKey)


@defer.inlineCallbacks
def createUser(emailId, displayName, jobTitle, timezone, passwd):
    localpart, domain = emailId.split("@")

    existingUser = yield Db.get_count(emailId, "userAuth")
    if not existingUser:
        orgId = yield getOrgKey(domain)
        if not orgId:
            orgId = utils.getUniqueKey()
            domains = {domain:''}
            basic = {"name":domain, "type":"org"}
            yield Db.batch_insert(orgId, "entities", {"basic":basic,"domains":domains})
            yield Db.insert(domain, "domainOrgMap", '', orgId)

        userId = yield utils.addUser(emailId, displayName, passwd,
                                     orgId, jobTitle, timezone)
        authinfo.username = userId
        authinfo.organization = orgId
    else:
        raise Exception("User already exists for " + emailId)


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], "e:n:t:z:")
        if len(opts) != 4:	# All args are required
            raise Exception
    except Exception as e:
	print e
        usage()
        sys.exit(2)

    options = dict(opts)
    emailId = options['-e']
    local, domain = emailId.split("@")
    displayName = options['-n']
    jobTitle = options['-t']
    timezone = options['-z']
    if not displayName or not jobTitle or not timezone or not local or not domain:
        raise Exception("Required params missing or empty\n"+usage())

    passwd = getpass.getpass('Password for '+emailId+': ')
    pwdrepeat = getpass.getpass('Repeat password: ')
    if passwd != pwdrepeat:
        raise Exception("Passwords don't match")

    log.startLogging(sys.stdout)
    d = createUser(emailId, displayName, jobTitle, timezone, passwd)
    d.addBoth(lambda x: reactor.stop())
    reactor.run()
