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
    sites = CfDef(KEYSPACE, 'sites', 'Super', 'BytesType', 'BytesType',
                  'Information on domains, sites and enabled applications')
    yield client.system_add_column_family(sites)

    yield client.batch_insert('synovel.com', 'sites', {'SiteInfo': {
                                'LicenseUsers': '20', 'CurrentUsers': '1'}})
    yield client.batch_insert('medhas.org' , 'sites', {'SiteInfo': {
                                'LicenseUsers': '20','CurrentUsers': '1'}})
    yield client.batch_insert('synovel.com/social', 'sites', { 'SiteInfo': {
                                'ParentSite': 'synovel.com' }})

    log.msg("Created column family: sites")

    #
    # Create and populate the "users" column family
    #
    users = CfDef(KEYSPACE, 'users', 'Super', 'BytesType', 'BytesType',
                  'User information - passwords, sessions and profile')
    yield client.system_add_column_family(users)
    yield client.batch_insert('synovel.com/u/prasad', 'users', {
                                'basic': {
                                    'Name': 'Prasad Sunkari',
                                    'CurrentLocation': 'Hyderabad',
                                    'Hometown': 'Hyderabad',
                                    'Sex': 'M',
                                    'Birthday': '19800817',
                                    'Description': 'Just another Tom, Dick and Harry'
                                },
                                'languages': {
                                    'Telugu': 'srw',
                                    'English': 'srw',
                                    'Hindi': 'rw'
                                },
                                'education': {
                                    '2003:IIIT Hyderabad': 'Bachelors',
                                    '1998:Sainik School Korukonda': 'Schooling'
                                },
                                'work': {
                                    '201012:Enterprise Social': 'Next generation enterprise social software',
                                    '200912:Web Client': 'The unfinished web based collaboration client',
                                    '200706:Spicebird': 'Desktop collaboration client'
                                },
                                'employers': {
                                    '2007:2003:Tata Consultancy Services': 'Description of work at Tata Consultancy Services',
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Trekking": "sports",
                                    "Open Source": "technology"
                                },
                                'contacts': {
                                    'WorkMail': 'prasad@synovel.com',
                                    'PersonalMail': 'prasad@medhas.org',
                                    'WorkPhone': '+914040044197',
                                    'MobilePhone': '+919848154689',
                                    'Address_Line01': 'PVN Colony, Malkajgiri',
                                    'Address_City': 'Hyderabad',
                                    'Address_State': 'Andhra Pradesh',
                                    'Address_Country': 'IN',
                                    'Address_PostalCode': '500047',
                                }})
    log.msg("Created column family: users")

    userauth = CfDef(KEYSPACE, 'userauth', 'Standard', 'BytesType', None,
                     'User authentication and authorizaton information')
    yield client.system_add_column_family(userauth)
    yield client.batch_insert('synovel.com/u/prasad', 'userauth', {
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
