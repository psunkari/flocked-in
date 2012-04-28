#!/usr/bin/python

import os
import sys
import optparse
import uuid
import cPickle as pickle
from boto.s3.connection import S3Connection

from telephus.cassandra import ttypes
from twisted.internet   import defer, reactor
from twisted.internet   import threads
from twisted.python     import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


@defer.inlineCallbacks
def createCF():
    attachmentVersions = ttypes.CfDef(KEYSPACE, "attachmentVersions", "Standard", "TimeUUIDType",
                                      None, "Time sorted list of versions of each attachment")
    yield db.system_add_column_family(attachmentVersions)


@defer.inlineCallbacks
def updateData():

    convIds = set()
    rows = yield db.get_range_slice('item_files', count=1000)

    for row in rows:
        convId = row.key
        convIds.add(convId)
        attachments = utils.supercolumnsToDict(row.columns)
        for attachmentId in attachments:
            for timeuuid in attachments[attachmentId]:
                encodedTimeUUID, aid, name, size, ftype = attachments[attachmentId][timeuuid].split(':')
                yield db.insert(attachmentId, "attachmentVersions", "%s:%s:%s:%s" %(aid, name, size, ftype), timeuuid)

    rows = yield db.get_range_slice('items', count=10000)
    for row in rows:
        itemId = row.key
        item = utils.supercolumnsToDict(row.columns)
        attachments = {}
        for attachmentId in item.get('attachments', {}):
            if len(item['attachments'][attachmentId].split(':')) == 4:
                x,name, size, ftype = item['attachments'][attachmentId].split(':')
                attachments[attachmentId] = "%s:%s:%s" %(name, size, ftype)
        if attachments:
            yield db.remove(itemId, 'items', super_column='attachments')
            yield db.batch_insert(itemId, "items", {"attachments": attachments})


    rows = yield db.get_range_slice('mConversations', count=10000)
    for row in rows:
        messageId = row.key
        message = utils.supercolumnsToDict(row.columns)
        attachments = {}
        print messageId
        for attachmentId in message.get('attachments', {}):
            if len(message['attachments'][attachmentId].split(':')) == 4:
                x,name, size, ftype = message['attachments'][attachmentId].split(':')
                attachments[attachmentId] = "%s:%s:%s" %(name, size, ftype)
        if attachments:
            yield db.remove(messageId, 'mConversations', super_column='attachments')
            yield db.batch_insert(messageId, "mConversations", {"attachments": attachments})







def main():
    parser = optparse.OptionParser()
    parser.add_option('-c', '--create', dest="create", action="store_true")
    parser.add_option('-d', '--update-data', dest='update', action="store_true")
    options, args = parser.parse_args()

    if options.create or options.update:
        log.startLogging(sys.stdout)
        db.startService()

        if options.create:
            d = createCF()
        elif options.update:
            d = updateData()

        def finish(x):
            db.stopService()
            reactor.stop()
        d.addErrback(log.err)
        d.addBoth(finish)

        reactor.run()

if __name__ == '__main__':
    main()
