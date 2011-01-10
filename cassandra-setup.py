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
    #
    # Create and populate the "sites" column family
    #
    sites = CfDef(KEYSPACE, 'sites', 'Super', 'UTF8Type', 'UTF8Type',
                  'Information on domains, sites and enabled applications')
    yield client.system_add_column_family(sites)

    yield client.batch_insert('synovel.com', 'sites', {'SiteInfo': {
                                'LicenseUsers': '20', 'CurrentUsers': '1'}})
    log.msg("Created column family: sites")

    #
    # Create and populate the "users" column family
    #
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
    log.msg("Created column family: users")

    userauth = CfDef(KEYSPACE, 'userauth', 'Standard', 'UTF8Type', None,
                     'User authentication and authorizaton information')
    yield client.system_add_column_family(userauth)
    yield client.batch_insert('synovel.com/u/prasad', 'userauth', {
                                'PasswordHash': 'c246ad314ab52745b71bb00f4608c82a'})
    yield client.batch_insert('synovel.com/u/ashok', 'userauth', {
                                'PasswordHash': 'c246ad314ab52745b71bb00f4608c82a'})
    log.msg("Created column family: userauth")

    reactor.stop()


if __name__ == '__main__':
    log.startLogging(sys.stdout)

    f = ManagedCassandraClientFactory(KEYSPACE)
    c = CassandraClient(f)
    setup(c)
    reactor.connectTCP(HOST, PORT, f)
    reactor.run()
