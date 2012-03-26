import uuid
import cPickle as pickle

from telephus.cassandra import ttypes
from twisted.internet   import defer

from social             import db, utils, errors, base, feed, _
from social             import people, notifications
from social.relations    import Relation
from social.settings    import saveAvatarItem
from social.constants   import PEOPLE_PER_PAGE


@defer.inlineCallbacks
def _notify(group, user):
    ""
    timeUUID = uuid.uuid1().bytes
    yield db.insert(group.id, "latest", user.id, timeUUID, "groups")


def _entityGroupMapColName(group):
    "return the string used as column-name in EntityGroup column family"
    return "%s:%s" % (group.basic['name'].lower(), group.id)


@defer.inlineCallbacks
def _removeFromPending(group, user):
    ""
    yield db.remove(group.id, "pendingConnections", "GI:%s" % (user.id))
    yield db.remove(user.id, "pendingConnections", "GO:%s" % (group.id))
    #also remove any group invites
    yield db.remove(user.id, "pendingConnections", "GI:%s" % (group.id))

    cols = yield db.get_slice(group.id, "latest", ['groups'])
    cols = utils.supercolumnsToDict(cols)
    for tuuid, key in cols.get('groups', {}).items():
        if key == user.id:
            yield db.remove(group.id, "latest", tuuid, 'groups')


@defer.inlineCallbacks
def _addMember(request, group, user):
    """Add a new member to the group.
    Add user to group followers, create a group-join activity item and push
    item to group, group-followers feed. Update user groups with new group.

    Keyword params:
    @group: entity object of the group
    @user: entity object of the user
    @request:

    """
    deferreds = []
    itemType = "activity"
    relation = Relation(user.id, [])
    if not getattr(user, 'basic', []):
        yield user.fetchData(['basic'])

    responseType = "I"
    acl = {"accept": {"groups": [group.id]}}
    _acl = pickle.dumps(acl)

    itemId = utils.getUniqueKey()
    colname = _entityGroupMapColName(group)
    yield db.insert(user.id, "entityGroupsMap", "", colname)
    yield db.insert(group.id, "groupMembers", itemId, user.id)
    item = yield utils.createNewItem(request, "activity", user,
                                     acl, "groupJoin")
    item["meta"]["target"] = group.id

    d1 = db.insert(group.id, "followers", "", user.id)
    d2 = db.batch_insert(itemId, 'items', item)
    d3 = feed.pushToFeed(group.id, item["meta"]["uuid"], itemId,
                         itemId, responseType, itemType, user.id)
    d4 = feed.pushToOthersFeed(user.id, user.basic['org'],
                                item["meta"]["uuid"], itemId,
                                itemId, _acl, responseType,
                                itemType, user.id, promoteActor=False)

    d5 = utils.updateDisplayNameIndex(user.id, [group.id],
                                      user.basic['name'], None)

    deferreds = [d1, d2, d3, d4, d5]
    yield defer.DeferredList(deferreds)


@defer.inlineCallbacks
def follow(group, user):
    """Add @user to @group followers

    Keyword params:
    @group: entity object of group
    @user: entity object of user
    """
    try:
        yield db.get(group.id, "groupMembers", user.id)
        yield db.insert(group.id, "followers", "", user.id)
        defer.returnValue(True)
    except ttypes.NotFoundException:
        return


@defer.inlineCallbacks
def unfollow(group, user):
    """Remove @user from @group followers

    Keyword params:
    @group: entity object of group
    @user: entity object of user
    """
    try:
        yield db.get(group.id, "groupMembers", user.id)
        yield db.remove(group.id, "followers", user.id)
        defer.returnValue(True)
    except ttypes.NotFoundException:
        return


@defer.inlineCallbacks
def subscribe(request, group, user, org):
    """Open group: add user to the group.
    Closed group: add a pending request, send a notification to group-admins.
    Raise an exception if user is blocked from joining the group.

    Keyword params:
    @org: org object
    @user: user object
    @group: group object
    @request:

    """
    cols = yield db.get_slice(group.id, "blockedUsers", [user.id])
    if cols:
        raise errors.PermissionDenied(_("You are banned from joining the group."))

    isNewMember = False
    pendingRequests = {}
    try:
        cols = yield db.get(group.id, "groupMembers", user.id)
    except ttypes.NotFoundException:
        if group.basic['access'] == "open":
            yield _addMember(request, group, user)
            yield _removeFromPending(group, user)
            isNewMember = True
        else:
            # Add to pending connections
            yield db.insert(user.id, "pendingConnections",
                            '', "GO:%s" % (group.id))
            yield db.insert(group.id, "pendingConnections",
                            '', "GI:%s" % (user.id))

            yield _notify(group, user)
            pendingRequests["GO:%s" % (group.id)] = user.id

            entities = base.EntitySet(group.admins.keys())
            yield entities.fetchData()

            entities.update({group.id: group, org.id: org, user.id: user})
            data = {"entities": entities, "groupName": group.basic['name']}
            yield notifications.notify(group.admins, ":GR", user.id, **data)
    defer.returnValue((isNewMember, pendingRequests))


@defer.inlineCallbacks
def unsubscribe(request, group, user):
    """Unsubscribe @user from @group.
    Remove the user from group-followers, group from user-groups,
    create a group-leave activity item and push item to group-followers
    and group feed. Remove the group from user display name indices.

    Raises an error if user is not member of group or when
    user is the only administrator of the group.

    keyword params:
    @user: entity object of user
    @group: entity object of the group
    @request:

    """
    try:
        yield db.get(group.id, "groupMembers", user.id)
    except ttypes.NotFoundException:
        raise errors.InvalidRequest(_("You are not a member of the group"))

    if len(getattr(group, 'admins', {}).keys()) == 1 \
       and user.id in group.admins:
        raise errors.InvalidRequest(_("You are the only administrator of this group"))

    colname = _entityGroupMapColName(group)
    itemType = "activity"
    responseType = "I"

    itemId = utils.getUniqueKey()
    acl = {"accept": {"groups": [group.id]}}
    _acl = pickle.dumps(acl)
    item = yield utils.createNewItem(request, itemType, user,
                                     acl, "groupLeave")
    item["meta"]["target"] = group.id

    d1 = db.remove(group.id, "followers", user.id)
    d2 = db.remove(user.id, "entityGroupsMap", colname)
    d3 = db.batch_insert(itemId, 'items', item)
    d4 = db.remove(group.id, "groupMembers", user.id)
    d5 = feed.pushToOthersFeed(user.id, user.basic['org'],
                               item["meta"]["uuid"], itemId, itemId, _acl,
                               responseType, itemType, user.id,
                               promoteActor=False)
    d6 = utils.updateDisplayNameIndex(user.id, [group.id], None,
                                      user.basic['name'])
    deferreds = [d1, d2, d3, d4, d5, d6]
    if user.id in group.admins:
        d7 = db.remove(group.id, "entities", user.id, "admins")
        d8 = db.remove(user.id, "entities", group.id, "adminOfGroups")
        deferreds.extend([d7, d8])

    yield defer.DeferredList(deferreds)


@defer.inlineCallbacks
def block(group, user, me):
    """Block user from joining a group/ sending further group-join requests.

    Keyword params:
    @me: entity object with my info
    @user: entity object of the user
    @group: entity object of the group
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')

    if me.id == user.id:
        raise errors.InvalidRequest(_("An administrator cannot ban himself/herself from the group"))
    try:
        yield db.get(group.id, "pendingConnections", "GI:%s" % (user.id))
        yield _removeFromPending(group, user)
        # Add user to blocked users
        yield db.insert(group.id, "blockedUsers", '', user.id)
        defer.returnValue(True)

    except ttypes.NotFoundException:
        # If the users is already a member, remove the user from the group
        colname = _entityGroupMapColName(group)
        yield db.remove(group.id, "groupMembers", user.id)
        yield db.remove(group.id, "followers", user.id)
        yield db.remove(user.id, "entityGroupsMap", colname)
        # Add user to blocked users
        yield db.insert(group.id, "blockedUsers", '', user.id)
        defer.returnValue(False)


@defer.inlineCallbacks
def unblock(group, user, me):
    """Unblock a blocked user.

    Keyword params:
    @me: entity object with my info
    @user: entity object of the user
    @group: entity object of the group
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')
    yield db.remove(group.id, "blockedUsers", user.id)


@defer.inlineCallbacks
def rejectRequest(group, user, me):
    """reject user's group-join request.
    Only group-admin can perform this action.

    Keyword params:
    @me:
    @user: user object
    @group: group object
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')

    try:
        yield db.get(group.id, "pendingConnections", "GI:%s" % (user.id))
        yield _removeFromPending(group, user)
        defer.returnValue(True)
    except ttypes.NotFoundException:
        pass
    defer.returnValue(False)


@defer.inlineCallbacks
def approveRequest(request, group, user, me):
    """accept a group-join request. Add the user to group-members.
    Only group-admin can perform this action.

    Keyword params:
    @me:
    @user: user object
    @group: group object
    @request:
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')

    try:
        yield db.get(group.id, "pendingConnections", "GI:%s" % (user.id))
        d1 = _removeFromPending(group, user)
        d2 = _addMember(request, group, user)

        data = {"entities": {group.id: group, user.id: user, me.id: me}}
        d3 = notifications.notify([user.id], ":GA", group.id, **data)

        yield defer.DeferredList([d1, d2, d3])
        defer.returnValue(True)

    except ttypes.NotFoundException:
        pass
    defer.returnValue(False)


@defer.inlineCallbacks
def cancelRequest(group, me):
    """cancel a join-group request

    Keyword params:
    @me:
    @group: group object
    """
    cols = yield db.get_slice(me.id, "pendingConnections",
                              ["GI:%s" % (group.id)])
    if cols:
        yield _removeFromPending(group, me)
        defer.returnValue(True)


@defer.inlineCallbacks
def removeUser(group, user, me):
    """Remove user from the group.
    Only group-admin can perform this action.

    Keyword params
    @me:
    @user: user object
    @group: group object
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')

    if len(getattr(group, 'admins', {})) == 1 and me.id == user.id:
        raise errors.InvalidRequest(_("You are currently the only administrator of this group"))

    try:
        cols = yield db.get(group.id, "groupMembers", user.id)
        itemId = cols.column.value
        username = user.basic['name']
        colName = _entityGroupMapColName(group)
        d1 = db.remove(itemId, "items")
        d2 = db.remove(group.id, "followers", user.id)

        d3 = db.remove(user.id, "entityGroupsMap", colName)
        d4 = db.remove(group.id, "groupMembers", user.id)
        d5 = utils.updateDisplayNameIndex(user.id, [group.id], '', username)
        deferreds = [d1, d2, d3, d4, d5]

        if user.id in group.admins:
            d6 = db.remove(group.id, 'entities', user.id, 'admins')
            d7 = db.remove(user.id, 'entities', group.id, 'adminOfGroups')
            deferreds.extend([d6, d7])

        #XXX: remove item from feed?
        yield defer.DeferredList(deferreds)
        defer.returnValue(True)

    except ttypes.NotFoundException:
        pass


@defer.inlineCallbacks
def makeAdmin(request, group, user, me):
    """make user admin of the group.
    Only an group-administrator can make an group-member and administrator.

    Keyword params:
    @request:
    @me:
    @user: user object
    @group: group object
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied(_('You are not an administrator of the group'))

    cols = yield db.get_slice(group.id, "groupMembers", [user.id])
    if not cols:
        raise errors.InvalidRequest(_('Only group member can become administrator'))

    if user.id in group.admins:
        defer.returnValue(None)

    yield db.insert(group.id, "entities", '', user.id, 'admins')
    yield db.insert(user.id, "entities", group.basic['name'],
                    group.id, "adminOfGroups")

    itemType = "activity"
    responseType = "I"
    acl = {"accept": {"groups": [group.id]}}
    _acl = pickle.dumps(acl)

    itemId = utils.getUniqueKey()
    item = yield utils.createNewItem(request, "activity", user,
                                     acl, "groupAdmin")
    item["meta"]["target"] = group.id

    d1 = db.batch_insert(itemId, 'items', item)
    d2 = feed.pushToFeed(group.id, item["meta"]["uuid"], itemId,
                         itemId, responseType, itemType, user.id)
    d3 = feed.pushToOthersFeed(user.id, user.basic['org'],
                                item["meta"]["uuid"], itemId, itemId,
                                _acl, responseType, itemType,
                                user.id, promoteActor=False)

    yield defer.DeferredList([d1, d2, d3])


@defer.inlineCallbacks
def removeAdmin(group, user, me):
    """strip admin privileges of user.
    Throw an error if @me is not group-admin or is the only admin and
    trying to removing self.
    Raise an exception when user is not a group-memeber or not a group-admin.

    Keyword params:
    @me:
    @user: user object
    @group: group object
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied(_('You are not an administrator of the group'))
    if me.id == user.id and len(group.admins.keys()) == 1:
        raise errors.InvalidRequest(_('You are the only administrator of the group'))

    cols = yield db.get_slice(group.id, "groupMembers", [user.id])
    if not cols:
        raise errors.InvalidRequest(_("User is not a member of the group"))

    if user.id not in group.admins:
        raise errors.InvalidRequest(_('User is not administrator of the group'))

    yield db.remove(group.id, "entities", user.id, "admins")
    yield db.remove(user.id, "entities", group.id, "adminOfGroups")


@defer.inlineCallbacks
def create(request, me, name, access, description, displayPic):
    """create a new group.
    add creator to the group members. make create administrator of the group.
    Note: No two groups in an organization should have same name.

    Keyword params:
    @request:
    @me:
    @name: name of the group.
    @access: group access type (open/closed).
    @description: description of the group.
    @displayPic: profile pic of the group.
    """
    if not name:
        raise errors.MissingParams([_("Group name")])

    cols = yield db.get_slice(me.basic['org'], "entityGroupsMap",
                              start=name.lower(), count=2)
    for col in cols:
        if col.column.name.split(':')[0] == name.lower():
            raise errors.InvalidGroupName(name)

    groupId = utils.getUniqueKey()
    group = base.Entity(groupId)
    meta = {"name": name, "type": "group",
            "access": access, "org": me.basic['org']}
    admins = {me.id: ''}
    if description:
        meta["desc"] = description

    if displayPic:
        avatar = yield saveAvatarItem(group.id, me.basic['org'], displayPic)
        meta["avatar"] = avatar

    group.update({'basic': meta, 'admins': admins})
    yield group.save()
    colname = _entityGroupMapColName(group)
    yield db.insert(me.id, "entities", name, group.id, 'adminOfGroups')
    yield db.insert(me.basic['org'], "entityGroupsMap", '', colname)
    yield _addMember(request, group, me)


@defer.inlineCallbacks
def edit(me, group, name, access, desc, displayPic):
    """update group meta info.
    Only group-admin can edit group meta info.

    Keyword params:
    @me:
    @group:
    @name: name of the group.
    @access: group access type (open/closed).
    @desc: description of the group.
    @displayPic: profile pic of the group.

    """
    if me.id not in group.admins:
        raise errors.PermissionDenied('Only administrator can edit group meta data')
    if name:
        start = name.lower() + ':'
        cols = yield db.get_slice(me.basic['org'], "entityGroupsMap",
                                  start=start, count=1)
        for col in cols:
            name_, groupId_ = col.column.name.split(':')
            if name_ == name.lower() and groupId_ != group.id:
                raise errors.InvalidGroupName(name)

    meta = {'basic': {}}
    if name and name != group.basic['name']:
        meta['basic']['name'] = name
    if desc and desc != group.basic.get('desc', ''):
        meta['basic']['desc'] = desc
    if access in ['closed', 'open'] and access != group.basic['access']:
        meta['basic']['access'] = access
    if displayPic:
        avatar = yield saveAvatarItem(group.id, me.basic['org'], displayPic)
        meta['basic']['avatar'] = avatar
    if name and name != group.basic["name"]:
        members = yield db.get_slice(group.id, "groupMembers")
        members = utils.columnsToDict(members).keys()
        entities = members + [me.basic['org']]
        oldColName = "%s:%s" % (group.basic["name"].lower(), group.id)
        colname = '%s:%s' % (name.lower(), group.id)
        mutations = {}
        for entity in entities:
            mutations[entity] = {'entityGroupsMap': {colname: '',
                                                     oldColName: None}}
        #XXX:notify group-members about the change in name
        yield db.batch_mutate(mutations)

    if meta['basic']:
        yield db.batch_insert(group.id, 'entities', meta)
    if not desc and group.basic.get('desc', ''):
        yield db.remove(group.id, "entities", 'desc', 'basic')
    if (not desc and group.basic.get('desc', '')) or meta['basic']:
        defer.returnValue(True)


@defer.inlineCallbacks
def getMembers(group, me, start=''):
    """get the member of the group starting with @start
    Only group-memeber can access the members list.

    Keyword params:
    @me:
    @group: group object
    @start: fetch users from start.
    """
    cols = yield db.get_slice(group.id, "groupMembers", [me.id])
    if not cols:
        raise errors.PermissionDenied(_("Access Denied"))

    users, relation, userIds, blockedUsers, nextPageStart, \
        prevPageStart = yield people.getPeople(me.id, group.id,
                                               me.basic['org'], start=start)
    defer.returnValue((users, relation, userIds, blockedUsers,
                       nextPageStart, prevPageStart))


@defer.inlineCallbacks
def getBlockedMembers(group, me, start='', count=PEOPLE_PER_PAGE):
    """get users blocked from a group.
    Only group-admins can view blocked users.

    Keyword params:
    @me:
    @group: group object
    @start: fetch users from @start
    @count: no.of users to be fetched.
    """
    if me.id not in group.admins:
        raise errors.PermissionDenied(_("Access Denied"))

    nextPageStart = ''
    prevPageStart = ''
    toFetchCount = count + 1
    cols = yield db.get_slice(group.id, "blockedUsers", start=start,
                                count=toFetchCount)
    blockedUsers = [col.column.name for col in cols]

    if start:
        prevCols = yield db.get_slice(group.id, "blockedUsers", start=start,
                                      reverse=True, count=toFetchCount)
        if len(prevCols) > 1:
            prevPageStart = utils.encodeKey(prevCols[-1].column.name)

    if len(blockedUsers) == toFetchCount:
        blockedUsers = blockedUsers[:PEOPLE_PER_PAGE]
        nextPageStart = utils.encodeKey(blockedUsers[-1])

    entities = base.EntitySet(blockedUsers)
    if blockedUsers:
        yield entities.fetchData()

    data = {"userIds": blockedUsers, "entities": entities,
            "prevPageStart": prevPageStart, "nextPageStart": nextPageStart}

    defer.returnValue(data)


@defer.inlineCallbacks
def getPendingRequests(group, me, start='', count=PEOPLE_PER_PAGE):
    """get the list of users who want to join the group.
    Only admin can view pending group requests.

    Keyword params:
    @me:
    @group: group object
    @start: start fetching from @start
    @count: no.of pending requests to fetch.
    """
    toFetchCount = count + 1
    nextPageStart = None
    prevPageStart = None

    if me.id not in group.admins:
        raise errors.PermissionDenied('Access Denied')

    cols = yield db.get_slice(group.id, "pendingConnections",
                              start=start, count=toFetchCount)
    userIds = [x.column.name.split(':')[1] for x in cols if len(x.column.name.split(':')) == 2]
    if len(userIds) == toFetchCount:
        nextPageStart = userIds[-1]
        userIds = userIds[0:count]
    entities = base.EntitySet(userIds)
    yield entities.fetchData()
    if start:
        cols = yield db.get_slice(group.id, "pendingConnections",
                                  start=start, count=toFetchCount,
                                  reverse=True)
        if len(cols) > 1:
            prevPageStart = cols[-1].column.name
    data = {'userIds': userIds, "entities": entities,
            "prevPageStart": prevPageStart,  "nextPageStart": nextPageStart}
    defer.returnValue(data)


@defer.inlineCallbacks
def getAllInvitations(me, start='', count=PEOPLE_PER_PAGE):
    """get all group invitations sent to @me starting from @start.

    Keyword params:
    @me:
    @start: fetch invitations starting from @start.
    @count: no.of invitations to be fetched.
    """
    if not start:
        start = 'GI'
    toFetchCount = count + 1
    nextPageStart = ''
    prevPageStart = ''
    toFetchEntities = set()

    cols = yield db.get_slice(me.id, "pendingConnections",
                              start=start, count=toFetchCount)
    groupIds = [x.column.name.split(':')[1] for x in cols if len(x.column.name.split(':')) == 2 and x.column.name.split(':')[0] == 'GI']
    pendingConnections = utils.columnsToDict(cols)
    if len(groupIds) == toFetchCount:
        groupIds = groupIds[:count]
        nextPageStart = utils.encodeKey(cols[-1].column.name)
    toFetchEntities.update(groupIds)
    cols = yield db.get_slice(me.id, "pendingConnections", reverse=True,
                              start=start, count=toFetchCount)
    cols = [x for x in cols if len(x.column.name.split(':')) == 2 and x.column.name.split(':')[1] == 'GI']

    if len(cols) > 1:
        prevPageStart = utils.encodeKey(cols[-1].column.name)

    entities = base.EntitySet(toFetchEntities)
    yield entities.fetchData()
    entities.update(me)
    defer.returnValue({"groupIds": groupIds, "entities": entities,
                        "myGroups": [], "prevPageStart": prevPageStart,
                        "nextPageStart": nextPageStart,
                        "pendingConnections": pendingConnections,
                        "groupFollowers": dict([(x, []) for x in groupIds])})


@defer.inlineCallbacks
def invite(group, me, user):
    """Invite an user to join a group.
    Only group-member can invite others to the group. Ignore if invited user
    is already a member of the group.

    Keyword params:
    @me:
    @user: user object
    @group: group object
    """
    try:
        yield db.get(group.id, "groupMembers", me.id)
    except ttypes.NotFoundException as e:
        raise e

    try:
        yield db.get(group.id, "groupMembers", user.id)
    except ttypes.NotFoundException:
        try:
            yield db.get(user.id, "pendingConnections", "GO:%s" % (group.id))
        except ttypes.NotFoundException:
            cols = yield db.get_slice(user.id, "pendingConnections",
                                      ["GI:%s" % (group.id)])
            invited_by = set()
            if cols:
                invited_by.update(cols[0].column.value.split(','))
            invited_by.add(me.id)
            yield db.insert(user.id, "pendingConnections",
                            ",".join(invited_by), "GI:%s" % (group.id))
            data = {"entities": {group.id: group, user.id: user, me.id: me},
                    "groupName": group.basic["name"]}
            yield notifications.notify([user.id], ":GI:%s" % (group.id),
                                        me.id, **data)


@defer.inlineCallbacks
def getGroupRequests(me, start='', count=PEOPLE_PER_PAGE):
    """get the list of users who want to join groups @me administers.

    Keyword params:
    @me:
    @start: start fetching from @start
    @count: no.of users/requests to fetch
    """
    userIds = []
    entities = {}
    nextPageStart = None
    prevPageStart = None

    cols = yield db.get_slice(me.id, "entities", super_column='adminOfGroups')
    managedGroupIds = [col.column.name for col in cols]
    if not managedGroupIds:
        data = {"userIds": [], "entities": {},
                "prevPageStart": None, "nextPageStart": None}
        defer.returnValue(data)

    startKey = ''
    startGroupId = managedGroupIds[0]
    if len(start.split(':')) == 2:
        userId, startGroupId = start.split(":")
        startKey = "GI:%s" % (userId)

    toFetchStart = startKey or "GI"
    toFetchGroup = startGroupId
    toFetchCount = count + 1
    toFetchEntities = set()

    index = 0
    try:
        index = managedGroupIds.index(toFetchGroup)
    except ValueError:
        pass

    while len(userIds) < toFetchCount:
        cols = yield db.get_slice(toFetchGroup, "pendingConnections",
                                  start=toFetchStart, count=toFetchCount)
        userIds.extend([(col.column.name.split(':')[1], toFetchGroup) for col in cols if len(col.column.name.split(':')) == 2 and col.column.name.split(':')[0] == "GI"])
        if len(userIds) >= toFetchCount:
            break
        if len(cols) < toFetchCount:
            if index + 1 < len(managedGroupIds):
                index = index + 1
                toFetchGroup = managedGroupIds[index]
                toFetchStart = 'GI'
            else:
                break

    if len(userIds) >= toFetchCount:
        nextPageStart = utils.encodeKey("%s:%s" % (userIds[count]))
        userIds = userIds[0:count]

    toFetchEntities.update([userId for userId, groupId in userIds])
    toFetchEntities.update([groupId for userId, groupId in userIds])

    entities = base.EntitySet(toFetchEntities)
    entities_d = entities.fetchData()

    try:
        toFetchGroup = startGroupId
        index = managedGroupIds.index(startGroupId)
        toFetchStart = startKey
    except ValueError:
        index = None

    if index is not None and start:
        tmpIds = []
        while len(tmpIds) < toFetchCount:
            cols = yield db.get_slice(toFetchGroup, "pendingConnections",
                                      start=toFetchStart, reverse=True,
                                      count=toFetchCount)
            tmpIds.extend([(col.column.name.split(':')[1], toFetchGroup) for col in cols if len(col.column.name.split(':')) == 2])

            if len(tmpIds) >= toFetchCount:
                tmpIds = tmpIds[0:toFetchCount]
                break
            if len(cols) < toFetchCount:
                if index - 1 >= 0:
                    index = index - 1
                    toFetchGroup = managedGroupIds[index]
                    toFetchStart = ''
                else:
                    break
        if len(tmpIds) > 1:
            prevPageStart = utils.encodeKey("%s:%s" % (tmpIds[-1]))

    yield entities_d
    entities.update(me)

    data = {"userIds": userIds, "entities": entities,
            "prevPageStart": prevPageStart, "nextPageStart": nextPageStart}
    defer.returnValue(data)


@defer.inlineCallbacks
def getGroups(me, entity, start='', count=PEOPLE_PER_PAGE):
    """get the groups of entity. (either groups of an organization
    or groups of an user)

    keyword params:
    @me:
    @entity: org/user
    start: fetch group from @start
    count: no.of groups to fetch.
    """
    toFetchCount = count + 1
    groups = {}
    groupIds = []
    myGroupsIds = []
    groupFollowers = {}
    pendingConnections = {}
    toFetchGroups = set()
    nextPageStart = ''
    prevPageStart = ''

    #TODO: list the groups in sorted order.
    cols = yield db.get_slice(entity.id, 'entityGroupsMap',
                              start=start, count=toFetchCount)
    groupIds = [x.column.name for x in cols]
    if len(groupIds) > count:
        nextPageStart = utils.encodeKey(groupIds[-1])
        groupIds = groupIds[0:count]
    toFetchGroups.update(set([y.split(':', 1)[1] for y in groupIds]))
    if entity.id == me.id:
        myGroupsIds = [x.split(':', 1)[1] for x in groupIds]
    elif groupIds:
        cols = yield db.get_slice(me.id, "entityGroupsMap", groupIds)
        myGroupsIds = [x.column.name.split(':', 1)[1] for x in cols]
    groupIds = [x.split(':', 1)[1] for x in groupIds]

    if start:
        cols = yield db.get_slice(entity.id, 'entityGroupsMap', start=start,
                                  count=toFetchCount, reverse=True)
        if len(cols) > 1:
            prevPageStart = utils.encodeKey(cols[-1].column.name)

    if toFetchGroups:
        groups = base.EntitySet(toFetchGroups)
        yield groups.fetchData()
        groupFollowers = yield db.multiget_slice(toFetchGroups, "followers",
                                                 names=[me.id])
        groupFollowers = utils.multiColumnsToDict(groupFollowers)
        columns = reduce(lambda x, y: x + y, [["GO:%s" % (x), "GI:%s" % (x)] for x in toFetchGroups])
        cols = yield db.get_slice(me.id, 'pendingConnections', columns)
        pendingConnections = utils.columnsToDict(cols)

    data = {"entities": groups, "groupIds": groupIds,
            "pendingConnections": pendingConnections,
            "myGroups": myGroupsIds, "groupFollowers": groupFollowers,
            "nextPageStart": nextPageStart, "prevPageStart": prevPageStart}
    defer.returnValue(data)


@defer.inlineCallbacks
def getManagedGroups(me, start, count=PEOPLE_PER_PAGE):
    """get all groups managed by me

    Keyword params:
    @me:
    @start: get groups from @start.
    @count: no.of groups to be fetched.
    """
    groups = {}
    groupIds = []
    myGroupsIds = []
    nextPageStart = ''
    prevPageStart = ''
    toFetchCount = count + 1
    toFetchGroups = set()
    groupFollowers = {}
    pendingConnections = {}

    try:
        cols = yield db.get_slice(me.id, "entities",
                                  super_column='adminOfGroups',
                                  start=start, count=toFetchCount)
        groupIds = [x.column.name for x in cols]
        toFetchGroups.update(set(groupIds))
        myGroupsIds = groupIds
        if len(groupIds) > count:
            nextPageStart = utils.encodeKey(groupIds[-1])
            groupIds = groupIds[0:count]
    except ttypes.NotFoundException:
        pass

    if start:
        cols = yield db.get_slice(me.id, "entities",
                                  super_column='adminOfGroups', start=start,
                                 count=toFetchCount, reverse=True)
        if len(cols) > 1:
            prevPageStart = utils.encodeKey(cols[-1].column.name)

    if toFetchGroups:
        groups = base.EntitySet(toFetchGroups)
        yield groups.fetchData()
        groupFollowers = yield db.multiget_slice(toFetchGroups, "followers", names=[me.id])
        groupFollowers = utils.multiColumnsToDict(groupFollowers)
        columns = reduce(lambda x, y: x + y, [["GO:%s" % (x), "GI:%s" % (x)] for x in toFetchGroups])
        cols = yield db.get_slice(me.id, 'pendingConnections', columns)
        pendingConnections = utils.columnsToDict(cols)

    data = {"entities": groups, "groupIds": groupIds,
            "pendingConnections": pendingConnections,
            "myGroups": myGroupsIds, "groupFollowers": groupFollowers,
            "nextPageStart": nextPageStart, "prevPageStart": prevPageStart}
    defer.returnValue(data)
