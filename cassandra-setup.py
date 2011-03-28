#!/usr/bin/python

import sys
import getopt
import uuid
import time

from telephus.protocol import ManagedCassandraClientFactory
from telephus.client import CassandraClient
from telephus.cassandra.ttypes import ColumnPath, ColumnParent, Column, SuperColumn, KsDef, CfDef
from twisted.internet import defer, reactor
from twisted.python import log

from social import Config, utils


HOST     = Config.get('Cassandra', 'Host')
PORT     = int(Config.get('Cassandra', 'Port'))
KEYSPACE = Config.get('Cassandra', 'Keyspace')


@defer.inlineCallbacks
def dropKeyspace(client):
    yield client.system_drop_keyspace(KEYSPACE)

@defer.inlineCallbacks
def createKeyspace(client):
    yield client.system_create_keyspace(KEYSPACE)

@defer.inlineCallbacks
def createColumnFamilies(client):
    # Information about organizations/groups/Users. Includes meta data
    # about the organization/groups/users (admins, logo, etc).
    entities = CfDef(KEYSPACE, 'entities', 'Super', 'UTF8Type', 'UTF8Type',
                  'Organization Information - name, avatar, admins...')
    yield client.system_add_column_family(entities)

    domainOrgMap = CfDef(KEYSPACE, "domainOrgMap", "Standard", "UTF8Type",
                         None, 'map from domain to org key')
    yield client.system_add_column_family(domainOrgMap)

    # List of users in the organization.
    orgUsers = CfDef(KEYSPACE, 'orgUsers', 'Standard', 'UTF8Type', None,
                        'List of users in an organization')
    yield client.system_add_column_family(orgUsers)

    # List of groups owned by the organization.  There will be other
    # groups that are owned by various users in the organization.
    orgGroups = CfDef(KEYSPACE, "orgGroups", "Standard", 'UTF8Type', None,
                        'List of groups owned by the organization')
    yield client.system_add_column_family(orgGroups)


    # Authentication information of the user.
    # Key is the e-mail address - contains userKey, orgKey, password etc;
    userAuth = CfDef(KEYSPACE, 'userAuth', 'Standard', 'UTF8Type', None,
                     'Authentication information about the user')
    yield client.system_add_column_family(userAuth)

    # User sessions
    sessions = CfDef(KEYSPACE, 'sessions', 'Super', 'BytesType', 'UTF8Type',
                     'Session information for logged in users')
    yield client.system_add_column_family(sessions)

    # Invitations sent out by existing users
    # Key is the e-mail of the recipient - contains inviteKey, sender's key etc;
    invitations = CfDef(KEYSPACE, "invitations", 'Standard', 'UTF8Type', None,
                        "List of invitations sent out by existing users")
    yield client.system_add_column_family(invitations)

    # Connections between users
    connections = CfDef(KEYSPACE, 'connections', 'Super', 'UTF8Type',
                        'UTF8Type', 'Established user connections')
    yield client.system_add_column_family(connections)

    # Connections sorted by tags
    connectionsByTag = CfDef(KEYSPACE, 'connectionsByTag', 'Super', 'UTF8Type',
                             'UTF8Type', 'User connections by tag')
    yield client.system_add_column_family(connectionsByTag)

    # Connections that are yet to be accepted
    pendingConnections = CfDef(KEYSPACE, "pendingConnections", "Standard",
                        "UTF8Type", None, "Pending connections")
    yield client.system_add_column_family(pendingConnections)

    # List of users that a user is following
    subscriptions = CfDef(KEYSPACE, 'subscriptions', 'Standard', 'UTF8Type',
                          None, 'User subscriptons')
    yield client.system_add_column_family(subscriptions)

    # List of users that are following a user
    followers = CfDef(KEYSPACE, 'followers', 'Standard', 'UTF8Type',
                      None, 'Followers of a user')
    yield client.system_add_column_family(followers)

    # List of enterprise links
    enterpriseLinks = CfDef(KEYSPACE, 'enterpriseLinks', 'Super', 'UTF8Type',
                            'UTF8Type', 'Official connections amoung users')
    yield client.system_add_column_family(enterpriseLinks)

    # List of groups that a user is a member of
    # groupKey => <subscribed>:<activityKey>
    userGroups = CfDef(KEYSPACE, 'userGroups', 'Standard', 'UTF8Type', None,
                       'List of groups that a user is a member of')
    yield client.system_add_column_family(userGroups)

    # List of members in a group
    # userKey => <subscribed>:<activityKey>
    groupMembers = CfDef(KEYSPACE, 'groupMembers', 'Standard', 'UTF8Type', None,
                         'List of members in a group')
    yield client.system_add_column_family(groupMembers)

    # All items and responses to items
    # Items include anything that can be shared, liked and commented upon.
    #    => Everything other than those that have special column families.
    items = CfDef(KEYSPACE, 'items', 'Super', 'UTF8Type', 'UTF8Type',
                  'All the items - mails, statuses, links, events etc;')
    yield client.system_add_column_family(items)

    itemLikes = CfDef(KEYSPACE, 'itemLikes', 'Standard', 'UTF8Type', None,
                      'List of likes per item')
    yield client.system_add_column_family(itemLikes)

    itemResponses = CfDef(KEYSPACE, 'itemResponses', 'Standard', 'TimeUUIDType',
                          None, 'List of responses per item')
    yield client.system_add_column_family(itemResponses)

    # Index of all items by a given user
    userItems = CfDef(KEYSPACE, 'userItems', 'Standard', 'TimeUUIDType', None,
                      'All items by a given user')
    yield client.system_add_column_family(userItems)

    # Index of posts by type
    for itemType in ['status', 'link', 'document']:
        columnFamily = "userItems_" + str(itemType)
        userItemsType = CfDef(KEYSPACE, columnFamily, 'Standard',
                              'TimeUUIDType', None,
                              '%s items posted by a given user'%(itemType))
        yield client.system_add_column_family(userItemsType)

    # Index of all posts accessible to a given user/group/organization
    feed = CfDef(KEYSPACE, 'feed', 'Standard', 'TimeUUIDType', None,
                 'A feed of all the items for user, group and organization')
    yield client.system_add_column_family(feed)

    feedItems = CfDef(KEYSPACE, "feedItems", "Super", "UTF8Type",
                      "TimeUUIDType", "Feed of items grouped by root itemId")
    yield client.system_add_column_family(feedItems)

    # Index of feed by type
    for itemType in ['status', 'link', 'document']:
        columnFamily = "feed_" + str(itemType)
        feedType = CfDef(KEYSPACE, columnFamily, 'Standard', 'TimeUUIDType',
                         None, 'Feed of %s items'%(itemType))
        yield client.system_add_column_family(feedType)

    # Polls
    userpolls = CfDef(KEYSPACE, 'userVotes', 'Standard', 'UTF8Type', None,
                                'Map of users to vote')
    yield client.system_add_column_family(userpolls)

    votes = CfDef(KEYSPACE, 'votes', 'Super', 'UTF8Type',
                        'UTF8Type', 'option - voter map')
    yield client.system_add_column_family(votes)

    # Events
    userEventResponse = CfDef(KEYSPACE, 'userEventResponse', 'Standard',
                              'UTF8Type', None,
                              'List of responses of users for events')
    eventInvitations = CfDef(KEYSPACE, "eventInvitations", "Super", "UTF8Type",
                             "TimeUUIDType", "")
    eventResponses = CfDef(KEYSPACE, 'eventResponses', 'Super', 'UTF8Type',
                           'UTF8Type', '')
    userEvents = CfDef(KEYSPACE, "userEvents", "Standard",
                       "TimeUUIDType", None, "")
    userEventInvitations = CfDef(KEYSPACE, "userEventInvitations", "Standard",
                                 "TimeUUIDType", None, "")
    yield client.system_add_column_family(userEventResponse)
    yield client.system_add_column_family(eventInvitations)
    yield client.system_add_column_family(eventResponses)
    yield client.system_add_column_family(userEvents)
    yield client.system_add_column_family(userEventInvitations)

    # Notifications
    notifications = CfDef(KEYSPACE, 'notifications', 'Standard', 'TimeUUIDType', None,
                         'A feed of all the items for user, group and organization')
    yield client.system_add_column_family(notifications)

    notificationItems = CfDef(KEYSPACE, "notificationItems", "Super", "UTF8Type",
                              "TimeUUIDType", "Notifications")
    yield client.system_add_column_family(notificationItems)

    # User's name indices
    displayNameIndex = CfDef(KEYSPACE, "displayNameIndex", "Standard",
                             "UTF8Type", None, "entityId to displayName:userId map")
    yield client.system_add_column_family(displayNameIndex)

    nameIndex = CfDef(KEYSPACE, "nameIndex", "Standard", "UTF8Type", None,
                      "entityId to (display name/firstname/lastname):userId map")
    yield client.system_add_column_family(nameIndex)


    # Tags
    orgTags = CfDef(KEYSPACE, "orgTags", "Super", "BytesType", "UTF8Type",
                    "List of tags by organization")
    tagFollowers = CfDef(KEYSPACE, "tagFollowers", "Standard", "BytesType",
                         None, "List of followers of each tag")
    tagItems = CfDef(KEYSPACE, "tagItems", "Standard", "TimeUUIDType", None,
                     "List of items in this tag")
    orgTagsByName = CfDef(KEYSPACE, "orgTagsByName", "Standard", "UTF8Type",
                          None, "List of tags by their name")
    yield client.system_add_column_family(orgTags)
    yield client.system_add_column_family(tagFollowers)
    yield client.system_add_column_family(tagItems)
    yield client.system_add_column_family(orgTagsByName)


@defer.inlineCallbacks
def addSampleData(client):
    # Create the organization
    exampleKey = utils.getUniqueKey()
    yield client.batch_insert(exampleKey, 'entities', {
                                'basic': {
                                    'name': 'Example Software',
                                    'type': 'org'
                                },
                                'domains': {
                                    'synovel.com': '',
                                    'example.org': ''
                                }})
    yield client.insert('synovel.com', 'domainOrgMap', '', exampleKey)
    yield client.insert('example.org', 'domainOrgMap', '', exampleKey)

    groupId = utils.getUniqueKey()
    meta = {"name": "Angry Birds",
            "desc":"",
            "orgKey":"PtW-7FSHEeCZAAAb_JBZ2A",
            "admin": "PueYplSHEeCZAAAb_JBZ2A",
            "access":"public",
            "type":"group"}
    yield client.batch_insert(groupId, "entities", {"basic":meta})
    yield client.insert(exampleKey, "orgGroups", '', groupId)

    # List of users in the organization
    prasadKey = utils.getUniqueKey()
    praveenKey = utils.getUniqueKey()
    ashokKey = utils.getUniqueKey()
    abhiKey = utils.getUniqueKey()
    rahulKey = utils.getUniqueKey()
    sandeepKey = utils.getUniqueKey()

    yield client.insert(exampleKey, "displayNameIndex", "", "prasad:"+prasadKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "ashok:"+ashokKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "rahul:"+rahulKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "abhi:"+abhiKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "sandy:"+sandeepKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "praveen:"+praveenKey)

    yield client.insert(exampleKey, "nameIndex", "", "prasad:"+prasadKey)
    yield client.insert(exampleKey, "nameIndex", "", "ashok:"+ashokKey)
    yield client.insert(exampleKey, "nameIndex", "", "rahul:"+rahulKey)
    yield client.insert(exampleKey, "nameIndex", "", "abhi:"+abhiKey)
    yield client.insert(exampleKey, "nameIndex", "", "sandeep:"+sandeepKey)
    yield client.insert(exampleKey, "nameIndex", "", "praveen:"+praveenKey)


    yield client.insert(exampleKey, "nameIndex", "", "pothana:"+praveenKey)
    yield client.insert(exampleKey, "nameIndex", "", "sunkari:"+prasadKey)
    yield client.insert(exampleKey, "nameIndex", "", "amaram:"+rahulKey)
    yield client.insert(exampleKey, "nameIndex", "", "Gudibandla:"+ashokKey)

    yield client.batch_insert(exampleKey, 'orgUsers', {
                                    prasadKey: '',
                                    praveenKey: '',
                                    ashokKey: '',
                                    abhiKey: '',
                                    rahulKey: '',
                                    sandeepKey:''
                                })

    # User profiles
    yield client.batch_insert(prasadKey, 'entities', {
                                'basic': {
                                    'name': 'Prasad',
                                    'firstname':"Prasad",
                                    "lastname": "Sunkari",
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Just another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
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
    yield client.batch_insert(ashokKey, 'entities', {
                                'basic': {
                                    'name': 'Ashok',
                                    "firstname": "Ashok",
                                    "lastname": "Gudibandla",
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Yet another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
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
    yield client.batch_insert(praveenKey, 'entities', {
                                'basic': {
                                    'name': 'Praveen',
                                    "firstname": "Praveen",
                                    "lastname": "Pothana",
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Yet another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
                                },
                                'expertise': {
                                    'Operations': ''
                                },
                                'languages': {
                                    'Telugu': 'srw',
                                    'English': 'srw'
                                },
                                'education': {
                                    '2008:IIIT Hyderabad': 'Graduation'
                                },
                                'work': {
                                    ':201012:calendar server': '',
                                },
                                'employers': {
                                    '2010:2008:EF': 'Lots of exciting work there!',
                                },
                                'contact': {
                                    'mail': 'praveen@synovel.com',
                                    'phone': '+917702228336'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Trekking": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'praveen.pothana@gmail.com',
                                    'mobile': '+917702228336',
                                    'hometown': 'cities/in/vijayawada',
                                    'currentcity': 'cities/in/hyderabad'
                                }})
    yield client.batch_insert(rahulKey, 'entities', {
                                'basic': {
                                    'name': 'Rahul',
                                    "firstname": "Rahul",
                                    "lastname": "Amaram",
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Just another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
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
                                    '2004:IIIT Hyderabad': 'Graduation',
                                    '1998:Some School Hyderabad': 'High school'
                                },
                                'work': {
                                    ':201012:Enterprise Social': 'Next generation enterprise social software',
                                    '201012:200912:Web Client': 'The unfinished web based collaboration client',
                                },
                                'employers': {
                                    '2007:2003:Tata Consultancy Services': 'Describe the four years of work at TCS',
                                },
                                'contact': {
                                    'mail': 'rahul@synovel.com',
                                    'phone': '+914040044197',
                                    'mobile': '+918989898989'
                                },
                                'interests': {
                                    "Wii": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'rahul@medhas.org',
                                    'mobile': '+918989898989',
                                    'hometown': 'in/hyderabad',
                                    'birthday': '19800817',
                                    'sex': 'M'
                                }})

    yield client.batch_insert(abhiKey, 'entities', {
                                'basic': {
                                    'name': 'Abhi',
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Just another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
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
                                    '2008:IIT Madras': 'Graduation',
                                    '2002:Some School Hyderabad': 'High school'
                                },
                                'work': {
                                    '201012:200912:Web Client': 'The unfinished web based collaboration client',
                                },
                                'employers': {
                                    '2008:2008: Google': 'Describe work at Google',
                                },
                                'contact': {
                                    'mail': 'abhishek@synovel.com',
                                    'phone': '+914040044197',
                                    'mobile': '+919911223344'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'abhishek@medhas.org',
                                    'mobile': '+919911223344',
                                    'hometown': 'in/hyderabad',
                                    'birthday': '19860215',
                                    'sex': 'M'
                                }})
    yield client.batch_insert(sandeepKey, 'entities', {
                                'basic': {
                                    'name': 'Sandy',
                                    "firstname": "Sandeep",
                                    'jobTitle': 'Hacker',
                                    'location': 'synovel.com/location/hyderabad',
                                    'desc': 'Just another Tom, Dick and Harry',
                                    'org': exampleKey,
                                    'type': "user"
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
                                    '2010: IIIT Hyderabad': 'Graduation',
                                    '2004:Some School Hyderabad': 'High school'
                                },
                                'work': {
                                    '201012:200912:Web Client': 'The unfinished web based collaboration client',
                                },
                                'employers': {
                                    '2008:2008: Google': 'Describe work at Google',
                                },
                                'contact': {
                                    'mail': 'sandeep@synovel.com',
                                    'phone': '+914040044197',
                                    'mobile': '+917755443311'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'mail': 'sandeep@medhas.org',
                                    'mobile': '+917755443311',
                                    'hometown': 'in/hyderabad',
                                    'birthday': '19870715',
                                    'sex': 'M'
                                }})


    # User authentication
    yield client.batch_insert('prasad@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': prasadKey
                                })
    yield client.batch_insert('ashok@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': ashokKey
                                })
    yield client.batch_insert('praveen@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': praveenKey
                                })
    yield client.batch_insert('rahul@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': rahulKey
                                })
    yield client.batch_insert('abhishek@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': abhiKey
                                })
    yield client.batch_insert('sandeep@synovel.com', 'userAuth', {
                                    'passwordHash': 'c246ad314ab52745b71bb00f4608c82a',
                                    'org': exampleKey,
                                    'user': sandeepKey
                                })


    # Connections between users
    prasadToAshokKey = utils.getUniqueKey()
    ashokToPrasadKey = utils.getUniqueKey()
    praveenToRahulKey = utils.getUniqueKey()
    rahulToPraveenKey = utils.getUniqueKey()
    yield client.batch_insert(prasadKey, "connections", {
                                    ashokKey: {
                                        "__default__": prasadToAshokKey
                                    }})
    yield client.batch_insert(ashokKey, "connections", {
                                    prasadKey: {
                                        "__default__": ashokToPrasadKey
                                    }})
    yield client.batch_insert(rahulKey, "connections", {
                                    praveenKey: {
                                        "__default__": rahulToPraveenKey
                                    }})
    yield client.batch_insert(praveenKey, "connections", {
                                    rahulKey: {
                                        "__default__": praveenToRahulKey
                                    }})
    yield client.insert(praveenKey, "displayNameIndex", "", "rahul:"+rahulKey)
    yield client.insert(rahulKey, "displayNameIndex", "", "praveen:"+praveenKey)
    yield client.insert(prasadKey, "displayNameIndex", "", "ashok:"+ashokKey)
    yield client.insert(ashokKey, "displayNameIndex", "", "prasad:"+prasadKey)

    # Create activity items and insert into feeds and userItems
    timeUUID = uuid.uuid1().bytes
    timestamp = str(int(time.time()))
    yield client.batch_insert(prasadToAshokKey, "items", {
                                    "meta": {
                                        "acl": "company",
                                        "owner": prasadKey,
                                        "type": "activity",
                                        "subType": "connection",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": ashokKey
                                    }})
    userItemValue = ":".join(["I", prasadToAshokKey, prasadToAshokKey, "activity", prasadKey, ""])
    yield client.insert(prasadKey, "userItems", userItemValue, timeUUID)
    yield client.insert(prasadKey, "feed", prasadToAshokKey, timeUUID)
    yield client.insert(prasadKey, "feedItems",
                        "I:%s:%s:%s" % (prasadKey, prasadToAshokKey, ashokKey),
                        timeUUID, prasadToAshokKey)

    timeUUID = uuid.uuid1().bytes
    yield client.batch_insert(ashokToPrasadKey, "items", {
                                    "meta": {
                                        "acl": "friends",
                                        "owner": ashokKey,
                                        "type": "activity",
                                        "subType": "connection",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": prasadKey
                                    }})
    userItemValue = ":".join(["I", ashokToPrasadKey, ashokToPrasadKey, "activity", ashokKey, ""])
    yield client.insert(ashokKey, "userItems", userItemValue, timeUUID)
    yield client.insert(ashokKey, "feed", ashokToPrasadKey, timeUUID)
    yield client.insert(ashokKey, "feedItems",
                        "I:%s:%s:%s" % (ashokKey, ashokToPrasadKey, prasadKey),
                        timeUUID, ashokToPrasadKey)

    timeUUID = uuid.uuid1().bytes
    timestamp = str(int(time.time()))
    yield client.batch_insert(praveenToRahulKey, "items", {
                                    "meta": {
                                        "acl": "friends",
                                        "owner": praveenKey,
                                        "type": "activity",
                                        "subType": "connection",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": rahulKey
                                    }})
    userItemValue = ":".join(["I", praveenToRahulKey, praveenToRahulKey, "activity", praveenKey, ""])
    yield client.insert(praveenKey, "userItems", userItemValue, timeUUID)
    yield client.insert(praveenKey, "feed", praveenToRahulKey, timeUUID)
    yield client.insert(praveenKey, "feedItems",
                                "I:%s:%s:%s" %(praveenKey, praveenToRahulKey, rahulKey),
                                timeUUID, praveenToRahulKey)


    timeUUID = uuid.uuid1().bytes
    yield client.batch_insert(rahulToPraveenKey, "items", {
                                    "meta": {
                                        "acl": "friends",
                                        "owner": rahulKey,
                                        "type": "activity",
                                        "subType": "connection",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": praveenKey
                                    }})
    userItemValue = ":".join(["I", rahulToPraveenKey, rahulToPraveenKey, "activity", rahulKey, ""])
    yield client.insert(rahulKey, "userItems", userItemValue, timeUUID)
    yield client.insert(rahulKey, "feed", rahulToPraveenKey, timeUUID)
    yield client.insert(rahulKey, "feedItems",
                                "I:%s:%s:%s" %(rahulKey, rahulToPraveenKey, praveenKey),
                                timeUUID, rahulToPraveenKey)



    # Subscriptions
    yield client.insert(praveenKey, "subscriptions", "", prasadKey)
    yield client.insert(prasadKey, "followers", "", praveenKey)

    # Create activity items and insert subscriptions into feeds and userItems
    praveenFollowingPrasadKey = utils.getUniqueKey()
    timeUUID = uuid.uuid1().bytes
    timestamp = str(int(time.time()))
    yield client.batch_insert(praveenFollowingPrasadKey, "items", {
                                    "meta": {
                                        "acl": "friends",
                                        "owner": praveenKey,
                                        "type": "activity",
                                        "subType": "following",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": prasadKey
                                    }})
    userItemValue = ":".join(["I", praveenFollowingPrasadKey, praveenFollowingPrasadKey, "activity", praveenKey, ""])
    yield client.insert(praveenKey, "userItems", userItemValue, timeUUID)
    yield client.insert(praveenKey, "feed", praveenFollowingPrasadKey, timeUUID)
    yield client.insert(praveenKey, "feedItems",
                        "I:%s:%s:%s" % (praveenKey, praveenFollowingPrasadKey, prasadKey),
                        timeUUID, praveenFollowingPrasadKey)


@defer.inlineCallbacks
def truncateColumnFamilies(client):
    for cf in ["entities", "orgUsers", "orgGroups", "userAuth",
               "sessions", "invitations", "connections",
               "connectionsByTag", "pendingConnections", "subscriptions",
               "followers", "enterpriseLinks", "userGroups", "groupMembers",
               "items", "itemLikes", "itemResponses", "userItems", "feed",
               "userItems_status", "userItems_link", "userItems_document",
               "feed_status", "feed_link","feed_document", "feedItems",
               "domainOrgMap", "userVotes", "votes", 'userEvents',
               'eventResponses', "userEventInvitations", "userEventResponse",
               'eventInvitations',"notifications", "notificationItems",
               "nameIndex", "displayNameIndex", "orgTags", "tagItems",
               "tagFollowers", "orgTagsByName"]:
        log.msg("Truncating: %s" % cf)
        yield client.truncate(cf)


if __name__ == '__main__':
    def usage():
        print("Usage: cassandra-setup.py <-c|-d|-t>")

    try:
        opts, args = getopt.getopt(sys.argv[1:], "cdt:")
        if len(opts) != 1:
            raise Exception
    except:
        usage()
        sys.exit(2)

    log.startLogging(sys.stdout)

    f = ManagedCassandraClientFactory(KEYSPACE)
    c = CassandraClient(f)

    deferreds = [];
    for (opt, val) in opts:
        if opt == "-c":
            deferreds.append(createColumnFamilies(c))
        elif opt == "-d":
            deferreds.append(addSampleData(c))
        elif opt == "-t" and val == "yes-remove-all-the-data":
            deferreds.append(truncateColumnFamilies(c))

    if len(deferreds) > 0:
        d = defer.DeferredList(deferreds)
        d.addBoth(lambda x: reactor.stop())

        reactor.connectTCP(HOST, PORT, f)
        reactor.run()
