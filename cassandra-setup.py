#!/usr/bin/python

import sys
import struct

from telephus.protocol import ManagedCassandraClientFactory
from telephus.client import CassandraClient
from telephus.cassandra.ttypes import ColumnPath, ColumnParent, Column, SuperColumn, KsDef, CfDef
from twisted.internet import defer, reactor
from twisted.python import log

from social import Config


HOST     = Config.get('Cassandra', 'Host')
PORT     = int(Config.get('Cassandra', 'Port'))
KEYSPACE = Config.get('Cassandra', 'Keyspace')


pack   = lambda x: struct.pack('!Q', x)
unpack = lambda x: struct.unpack('!Q', x)[0]


@defer.inlineCallbacks
def setup(client):
    # Information reg the domain/company
    sites = CfDef(KEYSPACE, 'sites', 'Super', 'UTF8Type', 'UTF8Type',
                  'Information on domains, sites and enabled applications')
    yield client.system_add_column_family(sites)
    yield client.batch_insert('synovel.com', 'sites', {'SiteInfo': {
                                'LicenseUsers': '20', 'CurrentUsers': '1'}})
    log.msg("Created sites")

    # User information
    users = CfDef(KEYSPACE, 'users', 'Super', 'UTF8Type', 'UTF8Type',
                  'User information - passwords, sessions and profile')
    yield client.system_add_column_family(users)
    yield client.batch_insert('synovel.com/u/prasad', 'users', {
                                'basic': {
                                    'name': 'Prasad Sunkari',
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Just another Tom, Dick and Harry',
                                },
                                'expertise': {
                                    'Open Source': '',
                                    'High Scalability': '',
                                    'Twisted Python': ''
                                },
                                'languages': {
                                    'Telugu': 'srw',
                                    'English': 'srw',
                                    'Hindi': 'rw'
                                },
                                'education': {
                                    '2003:IIIT Hyderabad': 'Graduation',
                                    '1998:Sainik School Korukonda': 'High school'
                                },
                                'work': {
                                    ':201012:Enterprise Social': 'Next generation enterprise social software',
                                    '201012:200912:Web Client': 'The unfinished web based collaboration client',
                                    '200912:200706:Spicebird': 'Desktop collaboration client'
                                },
                                'employers': {
                                    '2007:2003:Tata Consultancy Services': 'Describe the four years of work at TCS',
                                },
                                'contact': {
                                    'mail': 'prasad@synovel.com',
                                    'phone': '+914040044197',
                                    'mobile': '+919848154689'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Trekking": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'prasad@medhas.org',
                                    'mobile': '+918008123208',
                                    'hometown': 'in/hyderabad',
                                    'birthday': '19800817',
                                    'sex': 'M'
                                }})
    yield client.batch_insert('synovel.com/u/ashok', 'users', {
                                'basic': {
                                    'name': 'Ashok Gudibandla',
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Yet another Tom, Dick and Harry'
                                },
                                'expertise': {
                                    'Sales': '',
                                    'Marketing': '',
                                    'Operations': ''
                                },
                                'languages': {
                                    'Telugu': 'srw',
                                    'English': 'srw'
                                },
                                'education': {
                                    '2003:IIIT Hyderabad': 'Graduation'
                                },
                                'work': {
                                    ':201101:CollabSuite Sales': 'Sales and marketing of CollabSuite',
                                    '200908:200706:Spicebird': 'Desktop collaboration client'
                                },
                                'employers': {
                                    '2007:2005:Tata Consultancy Services': 'Worked on Swecha July\'07',
                                    '2005:2003:Mastek': 'Two years at Mastek'
                                },
                                'contact': {
                                    'mail': 'ashok@synovel.com',
                                    'phone': '+914040044197'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Trekking": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'gashok@gmail.com',
                                    'mobile': '+919848887540',
                                    'hometown': 'cities/in/guntur',
                                    'currentcity': 'cities/in/hyderabad'
                                }})
    log.msg("Created users")

    # User authentication - passwords and sessions
    userAuth = CfDef(KEYSPACE, 'userAuth', 'Standard', 'UTF8Type', None,
                     'User authentication and authorizaton information')
    yield client.system_add_column_family(userAuth)
    yield client.batch_insert('synovel.com/u/prasad', 'userAuth', {
                                'PasswordHash': 'c246ad314ab52745b71bb00f4608c82a'})
    yield client.batch_insert('synovel.com/u/ashok', 'userAuth', {
                                'PasswordHash': 'c246ad314ab52745b71bb00f4608c82a'})
    log.msg("Created userAuth")

    # Connections between users
    connections = CfDef(KEYSPACE, 'connections', 'Super', 'BytesType',
                        'BytesType', 'Established user connections')
    yield client.system_add_column_family(connections)

    connectionsByTag = CfDef(KEYSPACE, 'connectionsByTag', 'Super', 'BytesType',
                             'BytesType', 'User connections by type')
    yield client.system_add_column_family(connectionsByTag)
    log.msg("Created connections")

    # Subscriptions to changes by other people
    subscriptions = CfDef(KEYSPACE, 'subscriptions', 'Standard', 'BytesType',
                          None, 'User subscriptons')
    yield client.system_add_column_family(subscriptions)

    # Followers of a user
    followers = CfDef(KEYSPACE, 'followers', 'Standard', 'BytesType',
                      None, 'Followers of a user')
    yield client.system_add_column_family(followers)
    log.msg("Created subscriptions and followers")

    # Groups
    groups = CfDef(KEYSPACE, 'groups', 'Super', 'BytesType', 'BytesType',
                   'Groups of users')
    yield client.system_add_column_family(groups)
    log.msg("Created groups")

    # List of groups that a user is following
    userGroups = CfDef(KEYSPACE, 'userGroups', 'Standard', 'BytesType', None,
                       'List of groups that a user is a member of')
    yield client.system_add_column_family(userGroups)

    # All items and responses to items
    # Items include anything that can be shared, liked and commented upon.
    # => Everything other than those that have special column families.
    items = CfDef(KEYSPACE, 'items', 'Super', 'BytesType', 'BytesType',
                  'All the items - mails, statuses, links, events etc;')
    yield client.system_add_column_family(items)
    log.msg("Created items")

    # Index of all posts by a given user
    userItems = CfDef(KEYSPACE, 'userItems', 'Standard', 'TimeUUIDType', None,
                      'All items posted by a given user')
    yield client.system_add_column_family(userItems)
    log.msg("Created userposts")

    # Index of all posts accessible to a given user/domain/company
    feed = CfDef(KEYSPACE, 'feed', 'Standard', 'TimeUUIDType', None,
                 'A feed of all the items - both user and company')
    yield client.system_add_column_family(feed)
    log.msg("Created feed")

    reactor.stop()


if __name__ == '__main__':
    log.startLogging(sys.stdout)

    f = ManagedCassandraClientFactory(KEYSPACE)
    c = CassandraClient(f)
    setup(c)
    reactor.connectTCP(HOST, PORT, f)
    reactor.run()
