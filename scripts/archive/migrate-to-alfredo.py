#!/usr/bin/python

import os
import sys
import optparse
import uuid
import cPickle as pickle

from telephus.cassandra import ttypes
from twisted.internet   import defer, reactor
from twisted.python     import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


@defer.inlineCallbacks
def createCF():
    # Create column families required for file listing
    #    drop user_files CF
    #    create user_files entityFeed_files
    #
    yield db.system_drop_column_family('user_files')
    user_files = ttypes.CfDef(KEYSPACE, 'user_files', 'Standard',
                             'TimeUUIDType', None,
                             "List of files owned by the user")
    yield db.system_add_column_family(user_files)

    entityFeed_files = ttypes.CfDef(KEYSPACE, 'entityFeed_files',
                                'Standard', 'TimeUUIDType', None,
                                "List of files that appeared in entity's feed")
    yield db.system_add_column_family(entityFeed_files)

    #Remove User from network
    userSessionsMap = ttypes.CfDef(KEYSPACE, 'userSessionsMap', 'Standard',
                            'BytesType', None, 'userId-Session Map')
    yield db.system_add_column_family(userSessionsMap)

    deletedUsers = ttypes.CfDef(KEYSPACE, "deletedUsers", "Standard", "UTF8Type", None,
                         "List of users removed from the networks by admins.")
    yield db.system_add_column_family(deletedUsers)

    #Preset Tags

    orgPresetTags = ttypes.CfDef(KEYSPACE, "orgPresetTags", "Standard", "UTF8Type",
                          None, "List of preset tags. Only admin can create"
                          "or delete these tags. unlike normal tags these tags"
                          "will not be deleted automatically. On deletion it"
                          "behaves like a normal tag")
    yield db.system_add_column_family(orgPresetTags)

    #Keyword Monitoring
    keywords = ttypes.CfDef(KEYSPACE, 'keywords', 'Standard', 'UTF8Type',
                            None, "list of keywords to be monitored")
    yield db.system_add_column_family(keywords)

    originalKeywords = ttypes.CfDef(KEYSPACE, 'originalKeywords', 'Standard', 'UTF8Type',
                                    None, 'list of original keywords')
    yield db.system_add_column_family(originalKeywords)

    keywordItems = ttypes.CfDef(KEYSPACE, "keywordItems", "Standard", "TimeUUIDType",
                                None, "list of items which have a keyword monitored by admins")
    yield db.system_add_column_family(keywordItems)

    #API
    apps = ttypes.CfDef(KEYSPACE, "apps", "Super", "UTF8Type", "UTF8Type",
                 "Details of Applications registered for API Access")
    yield db.system_add_column_family(apps)

    appsByOwner = ttypes.CfDef(KEYSPACE, "appsByOwner", "Standard", "UTF8Type",
                        None, "List of applications registered by a User")
    yield db.system_add_column_family(appsByOwner)

    oAuthData = ttypes.CfDef(KEYSPACE, "oAuthData", "Standard", "UTF8Type",
                      None, "List of access, refresh tokens and auth codes")
    yield db.system_add_column_family(oAuthData)

    #
    # Create column families for poll indexing (in feeds and userItems)
    #
    userItemsType = ttypes.CfDef(KEYSPACE, 'userItems_poll', 'Standard',
                          'TimeUUIDType', None,
                          'poll items posted by a given user')
    yield db.system_add_column_family(userItemsType)

    feedType = ttypes.CfDef(KEYSPACE, 'feed_poll', 'Standard', 'TimeUUIDType',
                     None, 'Feed of poll items')
    yield db.system_add_column_family(feedType)

    #
    # Remove unused feed and userItems index
    #
    try:
        yield db.system_drop_column_family('feed_document')
    except: pass
    try:
        yield db.system_drop_column_family('userItems_document')
    except: pass


@defer.inlineCallbacks
def updateData():
    yield db.truncate('user_files')
    try:
        yield db.get('asdf', 'entityFeed_files', uuid.uuid1().bytes)
    except ttypes.InvalidRequestException as exception:
        log.msg(exception)
        raise Exception('entityFeed_files CF missing, create the CF')
    except ttypes.NotFoundException:
        pass
    entities = {}
    items = {}

    rows = yield db.get_range_slice('items', count=10000, reverse=True)
    for row in rows:
        itemId = row.key
        item = utils.supercolumnsToDict(row.columns)
        items[itemId]=item

    for itemId in items:
        item =  items[itemId]
        log.msg(itemId)
        if 'meta' not in item:
            continue

        # Add org to all items
        try:
            owner = item['meta']['owner']
            col = yield db.get(owner, "entities", 'org', 'basic')
            ownerOrgId = col.column.value
            yield db.insert(itemId, 'items', ownerOrgId, 'org', 'meta')
        except Exception as e:
            if item['meta'].get('type', '') == 'feedback':
                yield db.insert(itemId, 'items', owner, 'org', 'meta')

        # Fix ACLs
        if 'parent' not in item['meta']:
            acl = item['meta']['acl']
            convOwner = item['meta']['owner']
            convId = itemId

            if acl == 'company':
                col = yield db.get(convOwner, "entities", "org", "basic")
                ownerOrgId = col.column.value
                acl = pickle.dumps({"accept":{"orgs":[ownerOrgId]}})
                yield db.insert(convId, 'items', acl, 'acl', 'meta')
            else:
                try:
                    acl = pickle.loads(acl)
                    if 'accept' in acl and 'friends' in acl['accept'] and isinstance(acl['accept']['friends'], bool):
                        del acl['accept']['friends']
                        acl = pickle.dumps(acl)
                        yield db.insert(convId, 'items', acl, 'acl', 'meta')
                except :
                    log.msg('cannot unpack acl', acl)

        # Migrate files
        #    truncate user_files
        #    update user_files and entityFeed_files
        if 'owner' in item['meta'] and 'attachments' in item:
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
                    _entities = yield utils.expandAcl(ownerId, orgId, item['meta']['acl'],
                                                      itemId, ownerId, True)
                    for entityId in _entities:
                        yield db.insert(entityId, "entityFeed_files", val, timeuuid)

        # Migrate items
        # Meta fields in "link", "event" and "poll"
        if item['meta'].get('type', None) in ['link', 'poll', 'event']:
            itemMeta = item['meta']
            itemType = itemMeta['type']
            updated = {}

            if itemType == "link":
                if 'url' in itemMeta:
                    updated['link_url'] = itemMeta['url']
                if 'title' in itemMeta:
                    updated['link_title'] = itemMeta['title']
                if 'summary' in itemMeta:
                    updated['link_summary'] = itemMeta['summary']
                if 'imgSrc' in itemMeta:
                    updated['link_imgSrc'] = itemMeta['imgSrc']
                if 'embedType' in itemMeta:
                    updated['link_embedType'] = itemMeta['embedType']
                if 'embedSrc' in itemMeta:
                    updated['link_embedSrc'] = itemMeta['embedSrc']
                if 'embedHeight' in itemMeta:
                    updated['link_embedHeight'] = itemMeta['embedHeight']
                if 'embedWidth' in itemMeta:
                    updated['link_embedWidth'] = itemMeta['embedWidth']
            elif itemType == 'poll':
                if 'question' in itemMeta:
                    updated['comment'] = itemMeta['question']
            else:
                print 'Found an event:', itemId

            if updated:
                yield db.batch_insert(itemId, 'items', {'meta': updated})


    #
    # Create poll indexes for feed and userItems
    #
    rows = yield db.get_range_slice('entities', count=10000, reverse=True)
    mutations = {}
    for row in rows:
        entityId = row.key
        entity = utils.supercolumnsToDict(row.columns)

        if entity['basic']['type'] != 'user':
            continue

        d1 = db.get_slice(entityId, 'feed', count=10000)
        d2 = db.get_slice(entityId, 'userItems', count=10000)

        results = yield d1
        for col in results:
            value = col.column.value
            if value in items:
                if items.get(value, {}).get('meta', {}).get('type', '') == 'poll':
                    mutations.setdefault(entityId, {}).setdefault('feed_poll', {}).update({col.column.name: value})

        results = yield d2
        for col in results:
            value = col.column.value
            responseType, itemId, convId, convType, others = value.split(':', 4)
            if convType == 'poll':
                mutations.setdefault(entityId, {}).setdefault('userItems_poll', {}).update({col.column.name: value})
    yield db.batch_mutate(mutations)

    #Group type changed from public-private to open-closed.
    rows = yield db.get_range_slice('entityGroupsMap', count=1000)
    groupIds = set()
    for row in rows:
        for col in row.columns:
            name_, groupId = col.column.name.split(':')
            groupIds.add(groupId)

    cols = yield db.multiget_slice(groupIds, "entities")
    groups = utils.multiSuperColumnsToDict(cols)
    for groupId in groups:
        access = groups[groupId]['basic']['access'].lower()
        if access == 'public':
            yield db.insert(groupId, 'entities', 'open', 'access', 'basic')
        elif access.lower() == 'private':
            yield db.insert(groupId, 'entities', 'closed', 'access', 'basic')

    #Fix entityGroupsMap
    rows = yield db.get_range_slice('entityGroupsMap', count=1000)
    for row in rows:
        entityId = row.key
        for col in row.columns:
            name_, groupId = col.column.name.split(':')
            if col.column.name != '%s:%s'%(groups[groupId]['basic']['name'].lower(), groupId):
                yield db.remove(entityId, 'entityGroupsMap', col.column.name)
                yield db.insert(entityId, 'entityGroupsMap', '', '%s:%s' %(groups[groupId]['basic']['name'].lower(), groupId))


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
            d = updateData()

        def finish(x):
            db.stopService()
            reactor.stop()
        d.addErrback(log.err)
        d.addBoth(finish)

        reactor.run()

if __name__ == '__main__':
    main()

