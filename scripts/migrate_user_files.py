#!/usr/bin/python

import os
import sys
import optparse
import uuid

from telephus.cassandra import ttypes
from twisted.internet   import defer, reactor
from twisted.python     import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


@defer.inlineCallbacks
def createCF():
    """
        drop user_files CF
        create user_files entityFeed_files
    """
    yield db.system_drop_column_family('user_files')
    user_files = ttypes.CfDef(KEYSPACE, 'user_files', 'Standard',
                             'TimeUUIDType', None,
                             "List of files owned by the user")
    yield db.system_add_column_family(user_files)

    entityFeed_files = ttypes.CfDef(KEYSPACE, 'entityFeed_files',
                                'Standard', 'TimeUUIDType', None,
                                "List of files that appeared in entity's feed")
    yield db.system_add_column_family(entityFeed_files)


@defer.inlineCallbacks
def updateUserFiles():
    """
        truncate user_files
        update user_files and entityFeed_files
    """
    yield db.truncate('user_files')
    try:
        yield db.get('asdf', 'entityFeed_files', uuid.uuid1().bytes)
    except ttypes.InvalidRequestException as exception:
        log.msg(exception)
        raise Exception('entityFeed_files CF missing, create the CF')
    except ttypes.NotFoundException:
        pass
    entities = {}

    rows = yield db.get_range_slice('items', count=10000, reverse=True)
    for row in rows:
        itemId = row.key
        item = utils.supercolumnsToDict(row.columns)
        if 'meta' not in item:
            continue
        if 'owner' not in item['meta']:
            continue
        if 'attachments' not in item:
            continue
        ownerId = item['meta']['owner']
        if ownerId not in entities:
            cols = yield db.get_slice(ownerId, 'entities', ['basic'])
            entities.update({ownerId: utils.supercolumnsToDict(cols)})
        for attachmentId in item['attachments']:
            orgId = entities[ownerId]['basic']['org']
            timeuuid, name = item['attachments'][attachmentId].split(':')[:2]
            timeuuid = utils.decodeKey(timeuuid)
            val = '%s:%s:%s:%s' % (attachmentId, name, itemId, ownerId)
            yield db.insert(ownerId, "user_files", val, timeuuid)
            if 'parent' not in item['meta'] and item['meta'].get('acl', ''):
                entities = yield utils.expandAcl(ownerId, item['meta']['acl'],
                                                 itemId, ownerId, True)
                for entityId in entities:
                    yield db.insert(entityId, "entityFeed_files", val, timeuuid)


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
        if options.update:
            d = updateUserFiles()
        def finish(x):
            db.stopService()
            reactor.stop()
        d.addErrback(log.err)
        d.addBoth(finish)
        reactor.run()

if __name__ == '__main__':
    main()

