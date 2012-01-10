#!/usr/bin/python

import sys
import getopt
import uuid
import time
import pickle
import os

from telephus.protocol import ManagedCassandraClientFactory
from telephus.client import CassandraClient
from telephus.cassandra.ttypes import ColumnPath, ColumnParent, Column, SuperColumn, KsDef, CfDef
from twisted.internet import defer, reactor
from twisted.python import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")


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

    # Authentication information of the user.
    # Key is the e-mail address - contains userKey, orgKey, password etc;
    userAuth = CfDef(KEYSPACE, 'userAuth', 'Standard', 'UTF8Type', None,
                     'Authentication information about the user')
    yield client.system_add_column_family(userAuth)

    # User sessions
    sessions = CfDef(KEYSPACE, 'sessions', 'Standard', 'BytesType', None,
                     'Session information for logged in users')
    yield client.system_add_column_family(sessions)
    userSessionsMap = CfDef(KEYSPACE, 'userSessionsMap', 'Standard', 'BytesType', None,
                            'userId-Session Map')
    yield client.system_add_column_family(userSessionsMap)

    # Invitations sent out by existing users
    # Key is the e-mail of the recipient - contains inviteKey, sender's key etc;
    invitations = CfDef(KEYSPACE, "invitations", 'Super', 'UTF8Type', 'BytesType',
                        "List of invitations sent out by existing users")
    yield client.system_add_column_family(invitations)
    #
    invitationsSent = CfDef(KEYSPACE, "invitationsSent", "Standard", "BytesType", None,
                            "map of users to invitations")
    yield client.system_add_column_family(invitationsSent)

    # Temporary column family for storing email addresses of people
    # who expressed interest during the private beta.
    notifyOnRelease = CfDef(KEYSPACE, "notifyOnRelease", "Standard",
                            "UTF8Type", None, "Notify when public")
    yield client.system_add_column_family(notifyOnRelease)

    # Group connections that are yet to be accepted
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

    # entity -> group map
    entityGroupsMap = CfDef(KEYSPACE, 'entityGroupsMap', 'Standard', 'UTF8Type', None,
                            'entity->groups map')
    yield client.system_add_column_family(entityGroupsMap)

    blockedUsers = CfDef(KEYSPACE, "blockedUsers", "Standard", "UTF8Type", None,
                         "List of users blocked by admins from logging in or from joining the group"
                         "Blocked users will not be able to login/join the group.")
    yield client.system_add_column_family(blockedUsers)


    deletedUsers = CfDef(KEYSPACE, "deletedUsers", "Standard", "UTF8Type", None,
                         "List of users removed from the networks by admins.")
    yield client.system_add_column_family(deletedUsers)
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

    files = CfDef(KEYSPACE, 'files', 'Super', 'UTF8Type', 'UTF8Type',
                  'files and its details')
    yield client.system_add_column_family(files)

    tmp_files = CfDef(KEYSPACE, 'tmp_files', 'Standard', 'UTF8Type', None,
                  "tmp files and their details")
    yield client.system_add_column_family(tmp_files)

    item_files = CfDef(KEYSPACE, "item_files", 'Super', 'UTF8Type', 'TimeUUIDType',
                      'files and its version')
    yield client.system_add_column_family(item_files)

    user_files = CfDef(KEYSPACE, 'user_files', 'Standard', 'TimeUUIDType', None,
                  "List of files owned by the user")
    yield client.system_add_column_family(user_files)

    entityFeed_files = CfDef(KEYSPACE, 'entityFeed_files', 'Standard', 'TimeUUIDType', None,
                             "List of files that appeared in entity's feed")
    yield client.system_add_column_family(entityFeed_files)

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
    for itemType in ['status', 'link', 'question', 'poll']:
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
    for itemType in ['status', 'link', 'question', 'poll']:
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

    latest = CfDef(KEYSPACE, 'latest', 'Super', 'UTF8Type',
                                'TimeUUIDType', 'latest notifications for user')
    yield client.system_add_column_family(latest)

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

    messages = CfDef(KEYSPACE, "messages", "Super", "UTF8Type", "UTF8Type",
                      "A collection of all messages in this system")

    yield client.system_add_column_family(messages)

    mConversations = CfDef(KEYSPACE, "mConversations", "Super", "UTF8Type",
                          "UTF8Type", "A collection of all conversations")
    mAllConversations = CfDef(KEYSPACE, "mAllConversations", "Standard", "TimeUUIDType", None,
                     "list of all unread and read conversations of a user")
    mUnreadConversations = CfDef(KEYSPACE, "mUnreadConversations","Standard", "TimeUUIDType", None,
                    "list of all unread conversations of a user")
    mArchivedConversations = CfDef(KEYSPACE, "mArchivedConversations", "Standard", "TimeUUIDType", None,
                         "list of archived conversations of a user")
    mDeletedConversations = CfDef(KEYSPACE, "mDeletedConversations", "Standard", "TimeUUIDType", None,
                        "list of converstions marked for deletion of a user")
    mConvMessages = CfDef(KEYSPACE, "mConvMessages", "Standard", "TimeUUIDType", None,
                        "list of all messages in a conversation")
    mConvFolders = CfDef(KEYSPACE, "mConvFolders", "Super", "UTF8Type", "UTF8Type",
                        "list of folders in which a converstions belongs per user")

    yield client.system_add_column_family(mConversations)
    yield client.system_add_column_family(mAllConversations)
    yield client.system_add_column_family(mUnreadConversations)
    yield client.system_add_column_family(mArchivedConversations)
    yield client.system_add_column_family(mDeletedConversations)
    yield client.system_add_column_family(mConvMessages)
    yield client.system_add_column_family(mConvFolders)

    # Tags
    orgTags = CfDef(KEYSPACE, "orgTags", "Super", "BytesType", "UTF8Type",
                    "List of tags by organization")
    tagFollowers = CfDef(KEYSPACE, "tagFollowers", "Standard", "BytesType",
                         None, "List of followers of each tag")
    tagItems = CfDef(KEYSPACE, "tagItems", "Standard", "TimeUUIDType", None,
                     "List of items in this tag")
    orgTagsByName = CfDef(KEYSPACE, "orgTagsByName", "Standard", "UTF8Type",
                          None, "List of tags by their name")
    orgPresetTags = CfDef(KEYSPACE, "orgPresetTags", "Standard", "UTF8Type",
                          None, "List of preset tags. Only admin can create"
                          "or delete these tags. unlike normal tags these tags"
                          "will not be deleted automatically. On deletion it"
                          "behaves like a normal tag")
    yield client.system_add_column_family(orgTags)
    yield client.system_add_column_family(tagFollowers)
    yield client.system_add_column_family(tagItems)
    yield client.system_add_column_family(orgTagsByName)
    yield client.system_add_column_family(orgPresetTags)

    deletedConvs = CfDef(KEYSPACE, "deletedConvs", "Standard", "UTF8Type",
                         None, "list of deleted convs")
    yield client.system_add_column_family(deletedConvs)

    doNotSpam = CfDef(KEYSPACE, "doNotSpam", "Standard", "BytesType",
                      None, "list of email addresses that requested blocking")
    yield client.system_add_column_family(doNotSpam)
    suggestions = CfDef(KEYSPACE, "suggestions", "Standard", "IntegerType",
                        None, "Friend/Follow suggestions")
    yield client.system_add_column_family(suggestions)

    # API
    apps = CfDef(KEYSPACE, "apps", "Super", "UTF8Type", "UTF8Type",
                 "Details of Applications registered for API Access")

    appsByOwner = CfDef(KEYSPACE, "appsByOwner", "Standard", "UTF8Type",
                        None, "List of applications registered by a User")

    oAuthData = CfDef(KEYSPACE, "oAuthData", "Standard", "UTF8Type",
                      None, "List of access, refresh tokens and auth codes")

    yield client.system_add_column_family(apps)
    yield client.system_add_column_family(appsByOwner)
    yield client.system_add_column_family(oAuthData)

    keywords = CfDef(KEYSPACE, 'keywords', 'Standard', 'UTF8Type', None, "list of keywords to be monitored")
    yield client.system_add_column_family(keywords)

    originalKeywords = CfDef(KEYSPACE, 'originalKeywords', 'Standard', 'UTF8Type', None, 'list of original keywords')
    yield client.system_add_column_family(originalKeywords)

    keywordItems = CfDef(KEYSPACE, "keywordItems", "Standard", "TimeUUIDType",
                        None, "list of items which have a keyword monitored by admins")
    yield client.system_add_column_family(keywordItems)


@defer.inlineCallbacks
def addSampleData(client):
    #
    # Organization Name:
    #   Example Software Inc.
    # Users:
    #   Kevin King      (CEO)
    #   Ashok Ajax      (HR Manager)
    #   William Wiki    (Administrator)
    #   John Doe        (Programmer)
    #   Paul Foobar     (Programmer)
    #

    # The organization
    exampleKey = utils.getUniqueKey()

    # List of users in the organization
    kevinKey = utils.getUniqueKey()
    williamKey = utils.getUniqueKey()
    ashokKey = utils.getUniqueKey()
    johnKey = utils.getUniqueKey()
    paulKey = utils.getUniqueKey()
    adminKey = williamKey

    # Create the organization
    yield client.batch_insert(exampleKey, 'entities', {
                                'basic': {
                                    'name': 'Example Software',
                                    'type': 'org'
                                },
                                'domains': {
                                    'example.com': '',
                                    'example.org': ''
                                },
                                'admins': {adminKey: ''}})

    # Map domains to organization
    yield client.insert('example.com', 'domainOrgMap', '', exampleKey)
    yield client.insert('example.org', 'domainOrgMap', '', exampleKey)

    # Create groups
    managementGroupId = utils.getUniqueKey()
    yield client.batch_insert(managementGroupId, "entities", {
                                "basic": {
                                    "name": "Management",
                                    "desc": "Group of all executives involved in policy making",
                                    "org": exampleKey,
                                    "access": "private",
                                    "type": "group" },
                                "admins": {
                                    adminKey:''}})
    yield client.insert(exampleKey, "entityGroupsMap", '', 'management:%s'%(managementGroupId))

    programmersGroupId = utils.getUniqueKey()
    yield client.batch_insert(programmersGroupId, "entities", {
                                "basic": {
                                    "name": "Programmers",
                                    "desc": "Group of all programmers",
                                    "org": exampleKey,
                                    "access": "private",
                                    "type": "group" },
                                "admins": {
                                    adminKey:''}})
    yield client.insert(exampleKey, "entityGroupsMap", '', 'programmers:%s'%(programmersGroupId))

    # Index used to sort users in company user's list
    yield client.insert(exampleKey, "displayNameIndex", "", "kevin:"+kevinKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "ashok:"+ashokKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "paul:"+paulKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "john:"+johnKey)
    yield client.insert(exampleKey, "displayNameIndex", "", "william:"+williamKey)

    # Index used to search for users (mainly in autocomplete widgets)
    yield client.insert(exampleKey, "nameIndex", "", "kevin:"+kevinKey)
    yield client.insert(exampleKey, "nameIndex", "", "ashok:"+ashokKey)
    yield client.insert(exampleKey, "nameIndex", "", "paul:"+paulKey)
    yield client.insert(exampleKey, "nameIndex", "", "john:"+johnKey)
    yield client.insert(exampleKey, "nameIndex", "", "william:"+williamKey)

    yield client.insert(exampleKey, "nameIndex", "", "wiki:"+williamKey)
    yield client.insert(exampleKey, "nameIndex", "", "king:"+kevinKey)
    yield client.insert(exampleKey, "nameIndex", "", "foobar:"+paulKey)
    yield client.insert(exampleKey, "nameIndex", "", "ajax:"+ashokKey)

    # Add users to organization
    yield client.batch_insert(exampleKey, 'orgUsers', {
                                    kevinKey: '',
                                    williamKey: '',
                                    ashokKey: '',
                                    johnKey: '',
                                    paulKey: ''
                                })

    # User profiles
    yield client.batch_insert(kevinKey, 'entities', {
                                'basic': {
                                    'name': 'Kevin',
                                    'firstname':"Kevin",
                                    "lastname": "King",
                                    'jobTitle': 'Chief Executive Officer',
                                    'location': 'San Fransisco',
                                    'org': exampleKey,
                                    'type': "user",
                                    'timezone': 'America/Los_Angeles',
                                    'emailId': "kevin@example.com",
                                },
                                'languages': {
                                    'English': 'srw',
                                    'Spanish': 'srw',
                                    'Hindi': 'rw'
                                },
                                'schools': {
                                    '1996:Hraward Business School': 'Graduation'
                                },
                                'companies': {
                                    '2007:2003:Example Technology Services': 'Chief Financial Officer'
                                },
                                'contact': {
                                    'phone': '+11234567890',
                                    'mobile': '+12234567890'
                                },
                                'interests': {
                                    "Business Development": "",
                                    "Networking": ""
                                },
                                'personal': {
                                    'email': 'kevin@example.org',
                                    'hometown': 'New York',
                                    'birthday': '19700229',
                                    'sex': 'M'
                                }})
    yield client.batch_insert(ashokKey, 'entities', {
                                'basic': {
                                    'name': 'Ashok',
                                    "firstname": "Ashok",
                                    "lastname": "Ajax",
                                    'jobTitle': 'HR Manager',
                                    'location': 'San Fransisco',
                                    'timezone': 'America/Los_Angeles',
                                    'org': exampleKey,
                                    'type': "user",
                                    "emailId": "ashok@example.com"
                                },
                                'expertise': {
                                    'expertise': 'recruiting,hr-policies'
                                },
                                'languages': {
                                    'Telugu': 'srw',
                                    'Hindi': 'srw',
                                    'English': 'srw'
                                },
                                'schools': {
                                    '2003:Acpak School of Management': 'Post Graduation',
                                    '1998:Acpak Institute of Technology': 'Graduation'
                                },
                                'contact': {
                                    'phone': '+11234567890'
                                },
                                'personal': {
                                    'email': 'ashok@example.net',
                                    'hometown': 'Guntur, India'
                                }})
    yield client.batch_insert(williamKey, 'entities', {
                                'basic': {
                                    'name': 'William',
                                    "firstname": "William",
                                    "lastname": "Wiki",
                                    'jobTitle': 'Administrator',
                                    'location': 'San Fransisco',
                                    'org': exampleKey,
                                    'timezone': 'America/Los_Angeles',
                                    'type': "user",
                                    "emailId": "william@example.com"
                                },
                                'languages': {
                                    'English': 'srw',
                                    'German': 'srw'
                                },
                                'schools': {
                                    '2008:Mocha Frappe Institute of Technology': 'Graduation'
                                },
                                'companies': {
                                    '2010:2008:JohnDoe Corp': 'Chief Executive Officer'
                                },
                                'contact': {
                                    'phone': '+11234567890'
                                },
                                'interests': {
                                    "Cycling": "sports",
                                    "Trekking": "sports"
                                },
                                'personal': {
                                    'email': 'william@gmail.com',
                                    'hometown': 'Berlin, Germany',
                                    'currentcity': 'San Fransisco'
                                },
                                'adminOfGroups':{
                                    managementGroupId:'',
                                    programmersGroupId:''
                                }})
    yield client.batch_insert(paulKey, 'entities', {
                                'basic': {
                                    'name': 'Paul',
                                    "firstname": "Paul",
                                    "lastname": "Foobar",
                                    'jobTitle': 'Programmer',
                                    'location': 'Hyderabad, India',
                                    'org': exampleKey,
                                    'timezone': 'America/Los_Angeles',
                                    'type': "user",
                                    "emailId": "paul@example.com"
                                },
                                'languages': {
                                    'English': 'srw',
                                    'Hindi': 'rw'
                                },
                                'schools': {
                                    '2004:Green Tea Institute of Technology': 'Graduation'
                                },
                                'contact': {
                                    'phone': '+911234567890'
                                },
                                'interests': {
                                    "Wii": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'email': 'paul@example.org',
                                    'hometown': 'San Antonio',
                                    'birthday': '19820202',
                                    'sex': 'M'
                                }})

    yield client.batch_insert(johnKey, 'entities', {
                                'basic': {
                                    'name': 'John',
                                    'jobTitle': 'Programmer',
                                    'location': 'Hyderabad, India',
                                    'org': exampleKey,
                                    'timezone': 'America/Los_Angeles',
                                    'type': "user",
                                    "emailId": "john@example.com"
                                },
                                'languages': {
                                    'French': 'srw',
                                    'English': 'srw'
                                },
                                'schools': {
                                    '2008:Diced Onion Technology University': 'Graduation'
                                },
                                'contact': {
                                    'phone': '+911234567890'
                                },
                                'interests': {
                                    "Wii": "sports",
                                    "Open Source": "technology"
                                },
                                'personal': {
                                    'email': 'john@example.org',
                                    'hometown': 'Beechum County, Alabama',
                                    'birthday': '19780215',
                                    'sex': 'M'
                                }})

    # User authentication - password set to "example"
    yield client.batch_insert('kevin@example.com', 'userAuth', {
                                    'passwordHash': '1a79a4d60de6718e8e5b326e338ae533',
                                    'org': exampleKey,
                                    'user': kevinKey
                                })
    yield client.batch_insert('ashok@example.com', 'userAuth', {
                                    'passwordHash': '1a79a4d60de6718e8e5b326e338ae533',
                                    'org': exampleKey,
                                    'user': ashokKey
                                })
    yield client.batch_insert('william@example.com', 'userAuth', {
                                    'passwordHash': '1a79a4d60de6718e8e5b326e338ae533',
                                    'org': exampleKey,
                                    'user': williamKey,
                                    'isAdmin': 'True'
                                })
    yield client.batch_insert('paul@example.com', 'userAuth', {
                                    'passwordHash': '1a79a4d60de6718e8e5b326e338ae533',
                                    'org': exampleKey,
                                    'user': paulKey
                                })
    yield client.batch_insert('john@example.com', 'userAuth', {
                                    'passwordHash': '1a79a4d60de6718e8e5b326e338ae533',
                                    'org': exampleKey,
                                    'user': johnKey
                                })


    # Create activity items and insert into feeds and userItems
    acl_company = pickle.dumps({"accept":{"orgs": [exampleKey]}})

    # Subscriptions
    yield client.insert(williamKey, "subscriptions", "", kevinKey)
    yield client.insert(kevinKey, "followers", "", williamKey)

    # Create activity items and insert subscriptions into feeds and userItems
    williamFollowingKevinKey = utils.getUniqueKey()
    timeUUID = uuid.uuid1().bytes
    timestamp = str(int(time.time()))
    yield client.batch_insert(williamFollowingKevinKey, "items", {
                                    "meta": {
                                        "acl": acl_company,
                                        "owner": williamKey,
                                        "type": "activity",
                                        "subType": "following",
                                        "timestamp": timestamp,
                                        "uuid": timeUUID,
                                        "target": kevinKey
                                    }})
    userItemValue = ":".join(["I", williamFollowingKevinKey, williamFollowingKevinKey, "activity", williamKey, ""])
    yield client.insert(williamKey, "userItems", userItemValue, timeUUID)
    yield client.insert(williamKey, "feed", williamFollowingKevinKey, timeUUID)
    yield client.insert(williamKey, "feedItems",
                        "I:%s:%s:%s:" % (williamKey, williamFollowingKevinKey, kevinKey),
                        timeUUID, williamFollowingKevinKey)


@defer.inlineCallbacks
def truncateColumnFamilies(client):
    for cf in ["entities", "orgUsers", "userAuth",
               "sessions", "invitations", "pendingConnections", "subscriptions",
               "followers", "enterpriseLinks", "entityGroupsMap", "groupMembers",
               "items", "itemLikes", "itemResponses", "userItems", "feed",
               "userItems_status", "userItems_link", "userItems_poll",
               "feed_status", "feed_link","feed_poll", "feedItems",
               "domainOrgMap", "userVotes", "votes", 'userEvents',
               'eventResponses', "userEventInvitations", "userEventResponse",
               'eventInvitations',"notifications", "notificationItems",
               "nameIndex", "displayNameIndex", "orgTags", "tagItems",
               "tagFollowers", "orgTagsByName", "messages",
               "blockedUsers", "deletedConvs", "feed_question", 'userItems_question',
               "mConversations", "mAllConversations", "mUnreadConversations",
               "mArchivedConversations", "mDeletedConversations",
               "mConvMessages", "mConvFolders", "latest", "doNotSpam",
               "files", "tmp_files", "item_files", "invitationsSent",
               "user_files", "suggestions", "apps", "appsByOwner", "oAuthData",
               "userSessionsMap", "deletedUsers", "orgPresetTags",
               "keywords", "keywordItems", "originalKeywords"]:
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
    db.startService()

    d = None
    for (opt, val) in opts:
        if opt == "-c":
            d = createColumnFamilies(db)
        elif opt == "-d":
            d = addSampleData(db)
        elif opt == "-t" and val == "yes-remove-all-the-data":
            d = truncateColumnFamilies(db)

    if d:
        def finish(x):
            db.stopService()
            reactor.stop();
        d.addErrback(log.err)
        d.addBoth(finish)

        reactor.run()
