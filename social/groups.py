import uuid
from twisted.internet   import defer
from telephus.cassandra import ttypes
try:
    import cPickle as pickle
except:
    import pickle


from social             import base, db, utils, errors, feed, people, _
from social             import notifications
from social.constants   import PEOPLE_PER_PAGE
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log
from social.settings    import saveAvatarItem


class GroupsResource(base.BaseResource):
    isLeaf = True


    # Add a notification (TODO: and send mail notifications to admins
    # who prefer getting notifications on e-mail)
    @defer.inlineCallbacks
    def _notify(self, groupId, userId):
        timeUUID = uuid.uuid1().bytes
        yield db.insert(groupId, "latest", userId, timeUUID, "groups")


    # Remove notifications about a particular user.
    # XXX: Assuming that there wouldn't be too many items here.
    @defer.inlineCallbacks
    def _removeFromPending(self, groupId, userId):
        yield db.remove(groupId, "pendingConnections", "GI:%s"%(userId))
        yield db.remove(userId, "pendingConnections", "GO:%s"%(groupId))
        #also remove any group invites
        yield db.remove(userId, "pendingConnections", "GI:%s"%(groupId))

        cols = yield db.get_slice(groupId, "latest", ['groups'])
        cols = utils.supercolumnsToDict(cols)
        for tuuid, key in cols.get('groups', {}).items():
            if key == userId:
                yield db.remove(groupId, "latest", tuuid, 'groups')


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _follow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group")

        try:
            colname = "%s:%s" %(group["basic"]["name"].lower(), groupId)
            cols = yield db.get(myKey, "entityGroupsMap", colname)
            yield db.insert(groupId, "followers", "", myKey)
            args["groupId"] = groupId
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[myKey]}
            yield renderScriptBlock(request, "groups.mako", "group_actions",
                                    landing, "#group-actions-%s" %(groupId),
                                    "set", **args)
        except ttypes.NotFoundException:
            pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group")
        try:
            colname = "%s:%s" %(group["basic"]["name"].lower(), groupId)
            cols = yield db.get(myKey, "entityGroupsMap", colname)
            yield db.remove(groupId, "followers", myKey)

            args["groupId"] = groupId
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[]}
            yield renderScriptBlock(request, "groups.mako", "group_actions",
                                    landing, "#group-actions-%s" %(groupId),
                                    "set", **args)
        except ttypes.NotFoundException:
            pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addMember(self, request, groupId, userId, orgId, group):
        deferreds = []
        itemType = "activity"
        relation = Relation(userId, [])
        cols = yield db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)

        responseType = "I"
        acl = {"accept":{"groups":[groupId]}}
        _acl = pickle.dumps(acl)

        itemId = utils.getUniqueKey()
        colname = "%s:%s" %(group["basic"]["name"].lower(), groupId)
        yield db.insert(userId, "entityGroupsMap", "", colname)
        yield db.insert(groupId, "groupMembers", itemId, userId)
        item, attachments = yield utils.createNewItem(request, "activity",
                                                      userId, acl,
                                                      "groupJoin", orgId)
        item["meta"]["target"] = groupId

        d1 = db.insert(groupId, "followers", "", userId)
        d2 = db.batch_insert(itemId, 'items', item)
        d3 = feed.pushToFeed(groupId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)
        d4 = feed.pushToOthersFeed(userId, item["meta"]["uuid"], itemId, itemId,
                    _acl, responseType, itemType, userId, promoteActor=False)

        d5 = utils.updateDisplayNameIndex(userId, [groupId],
                                          userInfo['basic']['name'], None)

        deferreds = [d1, d2, d3, d4, d5]
        yield defer.DeferredList(deferreds)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _subscribe(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        groupId, group = yield utils.getValidEntityId(request, "id", "group", ["admins"])
        access = group["basic"]["access"]
        myGroups = []
        pendingRequests = {}
        groupFollowers = {groupId:[]}

        cols = yield db.get_slice(groupId, "blockedUsers", [myKey])
        if cols:
            raise errors.PermissionDenied(_("You are banned from joining this group."))

        colname = "%s:%s" %(group['basic']['name'].lower(), groupId)
        try:
            cols = yield db.get(myKey, "entityGroupsMap", colname)
        except ttypes.NotFoundException:
            if access == "open":
                yield self._addMember(request, groupId, myKey, myOrgId, group)
                myGroups.append(groupId)
                groupFollowers[groupId].append(myKey)
                yield self._removeFromPending(groupId, myKey)
            else:
                # Add to pending connections
                yield db.insert(myKey, "pendingConnections", '', "GO:%s" %(groupId))
                yield db.insert(groupId, "pendingConnections", '', "GI:%s"%(myKey))

                yield self._notify(groupId, myKey)
                pendingRequests[groupId] = myKey

                entities = yield db.multiget_slice(group["admins"], "entities", ["basic"])
                entities = utils.multiSuperColumnsToDict(entities)
                entities.update({groupId: group, args["orgKey"]: args["org"], myKey: args["me"]})
                data = {"entities": entities , "groupName": group['basic']['name']}
                yield notifications.notify(group["admins"], ":GR", myKey, **data)

            args["pendingConnections"] = pendingRequests
            args["groupFollowers"] = groupFollowers
            args["groupId"] = groupId
            args["myGroups"] = myGroups
            yield renderScriptBlock(request, "groups.mako", "group_actions",
                                    landing, "#group-actions-%s" %(groupId),
                                    "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _approve(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myKey in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            try:
                yield db.get(groupId, "pendingConnections", "GI:%s"%(userId))
                d1 = self._removeFromPending(groupId, userId)
                d2 = self._addMember(request, groupId, userId, myOrgId, group)
                d3 = renderScriptBlock(request, "groups.mako",
                                       "groupRequestActions", False,
                                       '#group-request-actions-%s-%s' %(userId, groupId),
                                       "set", args=[groupId, userId, "accept"])
                data = {"entities": {groupId: group, userId: user}}
                d4 = notifications.notify([userId], ":GA", groupId, **data)

                yield defer.DeferredList([d1, d2, d3, d4])

            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _reject(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myKey in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            try:
                yield db.get(groupId, "pendingConnections", "GI:%s"%(userId))
                yield self._removeFromPending(groupId, userId)
                yield renderScriptBlock(request, "groups.mako",
                                        "groupRequestActions", False,
                                        '#group-request-actions-%s-%s' %(userId, groupId),
                                        "set", args=[groupId, userId, "reject"])
            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _block(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myKey in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            if myKey == userId and myKey in group["admins"]:
                raise errors.InvalidRequest(_("An administrator cannot ban himself/herself from the group"))
            try:
                yield db.get(groupId, "pendingConnections", "GI:%s"%(userId))
                yield self._removeFromPending(groupId, userId)
                yield renderScriptBlock(request, "groups.mako",
                                        "groupRequestActions", False,
                                        '#group-request-actions-%s-%s' %(userId, groupId),
                                        "set", args=[groupId, userId, "block"])
            except ttypes.NotFoundException:
                # If the users is already a member, remove the user from the group
                colname = "%s:%s" %(group['basic']['name'].lower(), groupId)
                yield db.remove(groupId, "groupMembers", userId)
                yield db.remove(groupId, "followers", userId)
                yield db.remove(userId, "entityGroupsMap", colname)

            # Add user to blocked users
            yield db.insert(groupId, "blockedUsers", '', userId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unblock(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myKey in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            yield db.remove(groupId, "blockedUsers", userId)
            yield renderScriptBlock(request, "groups.mako",
                                    "groupRequestActions", False,
                                    '#group-request-actions-%s-%s' %(userId, groupId),
                                    "set", args=[groupId, userId, "unblock"])

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unsubscribe(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args["orgKey"]

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        colname = "%s:%s" %(group['basic']['name'].lower(), groupId)
        userGroup = yield db.get_slice(myId, "entityGroupsMap", [colname])
        if not userGroup:
            raise errors.InvalidRequest(_("You are not currently a member of this group"))

        if len(group.get('admins', [])) == 1 and myId in group['admins']:
            raise errors.InvalidRequest(_("You are currently the only administrator of this group"))

        itemType = "activity"
        responseType = "I"
        args["groupId"] = groupId
        args["myGroups"] = []
        args["groupFollowers"] = {groupId:[]}
        args["pendingConnections"] = []

        itemId = utils.getUniqueKey()
        acl = {"accept":{"groups":[groupId]}}
        _acl = pickle.dumps(acl)
        item, attachments = yield utils.createNewItem(request, itemType, myId,
                                   acl, "groupLeave", orgId)
        item["meta"]["target"] = groupId

        d1 = db.remove(groupId, "followers", myId)
        d2 = db.remove(myId, "entityGroupsMap", colname)
        d3 = db.batch_insert(itemId, 'items', item)
        d4 = db.remove(groupId, "groupMembers", myId)

        d5 = feed.pushToOthersFeed(myId, item["meta"]["uuid"], itemId, itemId,
                        _acl, responseType, itemType, myId, promoteActor=False)
        d6 = renderScriptBlock(request, "groups.mako", "group_actions",
                               landing, "#group-actions-%s" %(groupId),
                               "set", **args)

        d7 = utils.updateDisplayNameIndex(myId, [groupId], None,
                                          args['me']['basic']['name'])

        yield defer.DeferredList([d1, d2, d3, d4, d5, d6, d7])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _create(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]

        name = utils.getRequestArg(request, "name")
        description = utils.getRequestArg(request, "desc")
        access = utils.getRequestArg(request, "access") or "open"
        dp = utils.getRequestArg(request, "dp", sanitize=False)

        if not name:
            raise errors.MissingParams([_("Group name")])

        cols = yield db.get_slice(orgKey, "entityGroupsMap", start=name.lower(), count=2)
        for col in cols:
            if col.column.name.split(':')[0] == name.lower():
                #msg = _("Group ") + "'%s'"%(name) + _(" already exists")
                #request.write('$$.alerts.error("%s");' % msg)
                #XXX: Can't display alert message for some reason.
                raise errors.InvalidGroupName(name)

        groupId = utils.getUniqueKey()
        meta = {"name":name,
                "type":"group",
                "access":access,
                "org":args["orgKey"]}
        admins = {myKey:''}
        if description:
            meta["desc"] = description

        if dp:
            avatar = yield saveAvatarItem(groupId, dp)
            meta["avatar"] = avatar

        yield db.batch_insert(groupId, "entities", {"basic": meta,
                                                    "admins": admins})
        colname = "%s:%s" %(meta['name'].lower(), groupId)
        yield db.insert(myKey, "entities", name, groupId, 'adminOfGroups')
        yield db.insert(orgKey, "entityGroupsMap", '', colname)
        yield self._addMember(request, groupId, myKey, orgKey, {"basic":meta})

        response = """
                    <script>
                        parent.$$.alerts.info('%s');
                        parent.$.get('/ajax/notifications/new');
                        parent.$$.fetchUri('/groups');
                        parent.$('#add-user-wrapper').empty();
                    </script>
                   """ %(_("Group Created"))
        request.write(response)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderCreate(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgKey = args["orgKey"]
        args["menuId"] = "groups"

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
            yield renderScriptBlock(request, "groups.mako", "createGroup",
                                    landing, "#add-user-wrapper", "set", **args)
            script = """
                        $$.ui.bindFormSubmit('#group_form');
                        $('#group_form').html5form({messages: 'en'});
                     """

            script = "<script>%s</script>"%(script) if landing else script
            request.write(script);


    @defer.inlineCallbacks
    def _getPendingGroupRequests(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        cols = yield db.get_slice(myId, "entities", super_column='adminOfGroups')
        managedGroupIds = [col.column.name for col in cols]

        if not managedGroupIds:
            defer.returnValue(([], {}, None, None))

        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        startKey = ''
        startGroupId = managedGroupIds[0]
        if len(start.split(':')) == 2:
            userId, startGroupId = start.split(":")
            startKey = "GI:%s" %(userId)

        toFetchStart = startKey or "GI"
        toFetchGroup = startGroupId
        count = PEOPLE_PER_PAGE
        toFetchCount = count + 1
        nextPageStart = None
        prevPageStart = None
        toFetchEntities = set()

        userIds = []
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
                    index = index+1
                    toFetchGroup = managedGroupIds[index]
                    toFetchStart = 'GI'
                else:
                    break;

        if len(userIds) >= toFetchCount:
            nextPageStart = utils.encodeKey("%s:%s" %(userIds[count]))
            userIds = userIds[0:count]

        toFetchEntities.update([userId for userId, groupId in userIds])
        toFetchEntities.update([groupId for userId, groupId in userIds])
        entities_d = db.multiget_slice(toFetchEntities, "entities", ["basic"])

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
                    if index -1 >= 0:
                        index = index -1
                        toFetchGroup = managedGroupIds[index]
                        toFetchStart = ''
                    else:
                        break;
            if len(tmpIds) > 1:
                prevPageStart = utils.encodeKey("%s:%s"%(tmpIds[-1]))

        entities = yield entities_d
        entities = utils.multiSuperColumnsToDict(entities)

        defer.returnValue((userIds, entities, prevPageStart, nextPageStart))

    @defer.inlineCallbacks
    def _get_group_invitations(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        start = utils.getRequestArg(request, 'start') or 'GI'
        start = utils.decodeKey(start)
        count = PEOPLE_PER_PAGE
        toFetchCount = count + 1
        nextPageStart = None
        prevPageStart = None
        toFetchEntities = set()

        toFetchStart = start
        cols = yield db.get_slice(myId, "pendingConnections",
                                  start= toFetchStart, count= toFetchCount)
        groupIds = [x.column.name.split(':')[1] for x in cols if len(x.column.name.split(':'))==2 and x.column.name.split(':')[0] == 'GI']
        if len(groupIds) == toFetchCount:
            groupIds= groupIds[:count]
            nextPageStart = utils.encodeKey(cols[-1].column.name)
        toFetchEntities.update(groupIds)
        cols = yield db.get_slice(myId, "pendingConnections", reverse=True,
                                  start= toFetchStart, count= toFetchCount)
        cols = [x for x in cols if len(x.column.name.split(':'))==2 and x.column.name.split(':')[1] == 'GI']

        if len(cols) >1:
            prevPageStart = utils.encodeKey(cols[-1].column.name)
        toFetchEntities.add(myId)
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)

        defer.returnValue((groupIds, entities, prevPageStart, nextPageStart))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listGroups(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args["orgKey"]

        viewType = utils.getRequestArg(request, 'type') or 'myGroups'
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)

        viewTypes = ['myGroups', 'allGroups', 'adminGroups', 'pendingRequests', 'invitations']
        viewType = 'myGroups' if viewType not in viewTypes else viewType

        args["menuId"] = "groups"
        args['viewType']  = viewType

        cols = yield db.get_slice(myId, "entities", super_column='adminOfGroups')
        managedGroupIds = [col.column.name for col in cols]
        ##TODO: can we use getLatestCounts instead of fetching pendingConnections?
        cols = yield db.multiget_slice(managedGroupIds, "pendingConnections", count=1)
        cols = utils.multiColumnsToDict(cols)

        showPendingRequestsTab = sum([len(cols[groupId]) for groupId in cols]) > 0
        args["showPendingRequestsTab"] = showPendingRequestsTab

        counts = yield utils.getLatestCounts(request, False)
        groupRequestCount = args["groupRequestCount"] = counts["groups"]

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if viewType not in ['pendingRequests', 'invitations']:
            count = PEOPLE_PER_PAGE
            toFetchCount = count+1
            groups = {}
            groupIds = []
            myGroupsIds = []
            groupFollowers = {}
            pendingConnections = {}
            toFetchGroups = set()
            nextPageStart = ''
            prevPageStart = ''
            entityId = myId if viewType == 'myGroups' else orgId

            #TODO: list the groups in sorted order.
            if viewType in ['myGroups', 'allGroups']:
                cols = yield db.get_slice(entityId, 'entityGroupsMap',
                                          start=start, count=toFetchCount)
                groupIds = [x.column.name for x in cols]
                if len(groupIds) > count:
                    nextPageStart = utils.encodeKey(groupIds[-1])
                    groupIds = groupIds[0:count]
                toFetchGroups.update(set([y.split(':', 1)[1] for y in groupIds]))
                if viewType == "myGroups":
                    myGroupsIds = [x.split(':', 1)[1] for x in groupIds]
                elif groupIds:
                    cols = yield db.get_slice(myId, "entityGroupsMap", groupIds)
                    myGroupsIds = [x.column.name.split(':', 1)[1] for x in cols]
                groupIds = [x.split(':', 1)[1] for x in groupIds]
            elif viewType == 'adminGroups':
                try:
                    cols = yield db.get_slice(myId, "entities",
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
                if viewType in ['myGroups', 'allGroups']:
                    cols = yield db.get_slice(entityId, 'entityGroupsMap',
                                              start=start, count=toFetchCount,
                                              reverse=True)
                elif viewType == "adminGroups":
                    cols = yield db.get_slice(myId, "entities",
                                              super_column='adminOfGroups',
                                              start=start, count=toFetchCount,
                                              reverse=True)
                if len(cols) > 1:
                    prevPageStart = utils.encodeKey(cols[-1].column.name)

            if toFetchGroups:
                groups = yield db.multiget_slice(toFetchGroups, "entities", ["basic"])
                groups = utils.multiSuperColumnsToDict(groups)
                groupFollowers = yield db.multiget_slice(toFetchGroups, "followers", names=[myId])
                groupFollowers = utils.multiColumnsToDict(groupFollowers)
                cols = yield db.get_slice(myId, 'pendingConnections', ["GO:%s"%(x) for x in toFetchGroups])
                pendingConnections = dict((x.column.name.split(':')[1], x.column.value) for x in cols if len(x.column.name.split(':')) == 2)
            args["groups"] = groups
            args["groupIds"] = groupIds
            args["myGroups"] = myGroupsIds
            args["groupFollowers"] = groupFollowers
            args["pendingConnections"] = pendingConnections
            args['nextPageStart'] = nextPageStart
            args['prevPageStart'] = prevPageStart
        elif viewType == 'pendingRequests':
            userIds, entities, prevPageStart, nextPageStart = yield self._getPendingGroupRequests(request)
            args["userIds"] = userIds
            args["entities"] = entities
            args["prevPageStart"] = prevPageStart
            args["nextPageStart"] = nextPageStart
        elif viewType == 'invitations':
            groupIds, entities, prevPageStart, nextPageStart = yield self._get_group_invitations(request)
            args["groupIds"] = groupIds
            args["groups"] = entities
            args["prevPageStart"] = prevPageStart
            args["nextPageStart"] = nextPageStart
            args["pendingConnections"] = []
            args["myGroups"] = []
            args["groupFollowers"] = []

        if script:
            yield renderScriptBlock(request, "groups.mako", "viewOptions",
                                    landing, "#groups-view", "set", args=[viewType],
                                    showPendingRequestsTab=showPendingRequestsTab,
                                    groupRequestCount=groupRequestCount)
            if viewType == "pendingRequests":
                yield renderScriptBlock(request, "groups.mako", "allPendingRequests",
                                        landing, "#groups-wrapper", "set", **args)
            else:
                yield renderScriptBlock(request, "groups.mako", "listGroups",
                                        landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "paging",
                                    landing, "#groups-paging", "set", **args)

        if not script:
            yield render(request, "groups.mako", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listGroupMembers(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group")
        start = utils.getRequestArg(request, 'start') or ''

        fromFetchMore = ((not landing) and (not appchange) and start)
        args["menuId"] = "groups"

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users, relation, userIds, blockedUsers, nextPageStart,\
            prevPageStart = yield people.getPeople(myKey, groupId,
                                                   args['orgKey'], start=start)
        args["relations"] = relation
        args["entities"] = users
        args["userIds"] = userIds
        args["blockedUsers"] = blockedUsers
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["groupId"] = groupId
        args["heading"] = "Members"

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "listGroupMembers",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "paging",
                                landing, "#groups-paging", "set", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listPendingSubscriptions(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        start = utils.getRequestArg(request, 'start') or 'GI'
        count = PEOPLE_PER_PAGE
        toFetchCount = count+1
        nextPageStart = None
        prevPageStart = None

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        args["menuId"] = "groups"

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            cols = yield db.get_slice(groupId, "pendingConnections",
                                      start=start, count=toFetchCount)
            userIds = [x.column.name.split(':')[1] for x in cols if len(x.column.name.split(':'))==2]
            if len(userIds) == toFetchCount:
                nextPageStart = userIds[-1]
                userIds = userIds[0:count]
            cols = yield db.multiget_slice(userIds, "entities", ["basic"])
            users = utils.multiSuperColumnsToDict(cols)
            if start:
                cols = yield db.get_slice(groupId, "pendingConnections",
                                          start=start, count=toFetchCount,
                                          reverse=True)
                if len(cols) >1:
                    prevPageStart = cols[-1].column.name

            args["entities"] = users
            args["userIds"] = userIds
        else:
            args["entities"] = {}
            args["userIds"] = []

        args["heading"] = "Pending Requests"
        args["groupId"] = groupId
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["entities"][groupId] = group

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "pendingRequests",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, 'groups.mako', "pendingRequestsPaging",
                                    landing, "#groups-paging", "set", **args)



    @defer.inlineCallbacks
    def _invite(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        args["groupId"] = groupId
        args["heading"] = group["basic"]["name"]

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        try:
            yield db.get(groupId, "groupMembers", myId)
        except ttypes.NotFoundException:
            request.write('$$.alerts.error("You should be member of the group to Invite Others");')
            defer.returnValue(None)

        userId, user = yield utils.getValidEntityId(request, "invitee", "user")
        #ignore the request if user is already a member
        try:
            yield db.get(groupId, "groupMembers", userId)
        except ttypes.NotFoundException:
            cols = yield db.get_slice(userId, "pendingConnections", ["GI:%s"%(groupId)])
            invited_by = set()
            if cols:
                invited_by.update(cols[0].column.value.split(','))
            invited_by.add(myId)
            yield db.insert(userId, "pendingConnections", ",".join(invited_by), "GI:%s"%(groupId))
            data = {"entities": {groupId: group, userId: user, myId:args["me"]},
                    "groupName": group["basic"]["name"]}
            yield notifications.notify([userId], ":GI:%s"%(groupId), myId, **data)
        finally:
            refreshFeedScript = """
                $("#group_add_invitee").attr("value", "");
                $$.alerts.info("%s is invited to the %s");""" %(user["basic"]["name"], group["basic"]["name"])
            request.write(refreshFeedScript)


    @defer.inlineCallbacks
    def _renderInviteMembers(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        args["groupId"]=groupId
        args["heading"] = group["basic"]["name"]

        if script and landing:
            yield render(request, "groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
            yield renderScriptBlock(request, "groups.mako", "inviteMembers",
                                    landing, "#groups-wrapper", "set", **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listGroups(request)
        elif segmentCount == 1:
            if request.postpath[0] == "members":
                d = self._listGroupMembers(request)
            elif request.postpath[0] == "create":
                d = self._renderCreate(request)
            elif request.postpath[0] == "pending":
                d = self._listPendingSubscriptions(request)

        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1:
            action = request.postpath[0]
            if action == 'approve':
                d = self._approve(request)
            elif action == 'reject':
                d = self._reject(request)
            elif action == 'block':
                d = self._block(request)
            elif action == 'unblock':
                d = self._unblock(request)
            elif action == 'invite':
                d = self._invite(request)
            elif action == 'follow':
                d = self._follow(request)
            elif action == 'unfollow':
                d = self._unfollow(request)
            elif action == 'subscribe':
                d = self._subscribe(request)
            elif action == 'unsubscribe':
                d = self._unsubscribe(request)
            elif action == 'create':
                d = self._create(request)
            def _updatePendingGroupRequestCount(ign):
                def _update_count(counts):
                    pendingRequestCount = counts['groups'] if counts.get('groups', 0)!= 0 else ''
                    request.write("$('#pending-group-requests-count').html('%s');"%(pendingRequestCount))
                d01 = utils.render_LatestCounts(request, False, False)
                d01.addCallback(_update_count)
                return d01
            if action not in ["create"]:
                d.addCallback(_updatePendingGroupRequestCount)

        return self._epilogue(request, d)
