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
    users = CfDef(KEYSPACE, 'users', 'Standard', 'BytesType', None,
                  'User information - passwords, sessions and profile')
    yield client.system_add_column_family(users)
    yield client.batch_insert('synovel.com/u/prasad', 'users', {
                                'CurrentLocation': 'Hyderabad',
                                'Hometown': 'Hyderabad',
                                'Sex': 'M',
                                'Birthday': '19800817',
                                'Description': 'One of Tom, Dick and Harry',
                                'Language01': 'Telugu',
                                'Language02': 'English',
                                'Language03': 'Hindi',
                                'Education01_Start': '1991',
                                'Education01_End': '1998',
                                'Education01_What': 'Schooling',
                                'Education01_Where': 'Sainik School, Korukonda',
                                'Education01_More': '...',
                                'Education02_Start': '1999',
                                'Education02_End': '2003',
                                'Education02_What': 'Bachelors',
                                'Education02_Where': 'IIIT, Hyderabad',
                                'Education02_More': '...',
                                'CurrentWork01_Start': '20101201',
                                'CurrentWork01_Title': 'Enterprise Social',
                                'CurrentWork01_More': 'NextGen Enterprise',
                                'Work01_Start': '20091201',
                                'Work01_End': '20101130',
                                'Work01_Title': 'Web collaboration client',
                                'Work01_More': 'Unfinished!',
                                'Work02_Start': '20070601',
                                'Work02_End': '20101201',
                                'Work02_Title': 'Spicebird',
                                'Work02_More': 'Collaboration client',
                                'Experience01_Company': 'TCS',
                                'Experience01_Start': '200306',
                                'Experience01_End': '200705',
                                'Experience01_More': '...',
                                'Interests01_Area': 'Sports & Adventure',
                                'Interests01_Item': 'Cycling',
                                'Interests02_Area': 'Sports & Adventure',
                                'Interests02_Item': 'Trekking',
                                'Interests03_Area': 'Technology',
                                'Interests03_Item': 'Open Source',
                                'WorkMailId': 'prasad@synovel.com',
                                'PersonalMailId': 'prasad@medhas.org',
                                'WorkPhone': '+914040044197',
                                'MobilePhone': '+919848154689',
                                'Address_Line01': 'PVN Colony, Malkajgiri',
                                'Address_City': 'Hyderabad',
                                'Address_State': 'Andhra Pradesh',
                                'Address_Country': 'IN',
                                'Address_PostalCode': '500047',
                                'PasswordHash': 'c246ad314ab52745b71bb00f4608c82a'})
    log.msg("Created column family: users")

    reactor.stop()


if __name__ == '__main__':
    log.startLogging(sys.stdout)

    f = ManagedCassandraClientFactory(KEYSPACE)
    c = CassandraClient(f)
    setup(c)
    reactor.connectTCP(HOST, PORT, f)
    reactor.run()
