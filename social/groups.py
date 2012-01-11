import uuid
from twisted.internet   import defer
from telephus.cassandra import ttypes
try:
    import cPickle as pickle
except:
    import pickle


from social             import base, db, utils, errors, feed, people, _, plugins
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
        myId = request.getSession(IAuthInfo).username
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group")

        try:
            colname = "%s:%s" %(group["basic"]["name"].lower(), groupId)
            cols = yield db.get(myId, "entityGroupsMap", colname)
            yield db.insert(groupId, "followers", "", myId)
            args = {"groupId": groupId}
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[myId]}
            args["entities"] = {groupId: group}
            args['myId'] = myId
            yield renderScriptBlock(request, "group-feed.mako", "group_actions",
                                    landing, "#group-actions-%s" %(groupId),
                                    "set", **args)
        except ttypes.NotFoundException:
            pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, request):
        myId = request.getSession(IAuthInfo).username
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group")
        try:
            colname = "%s:%s" %(group["basic"]["name"].lower(), groupId)
            cols = yield db.get(myId, "entityGroupsMap", colname)
            yield db.remove(groupId, "followers", myId)

            args = {"groupId": groupId}
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[]}
            args["entities"] = {groupId: group}
            args['myId'] = myId
            yield renderScriptBlock(request, "group-feed.mako", "group_actions",
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
                                                      userId, orgId, acl,
                                                      "groupJoin")
        item["meta"]["target"] = groupId

        d1 = db.insert(groupId, "followers", "", userId)
        d2 = db.batch_insert(itemId, 'items', item)
        d3 = feed.pushToFeed(groupId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)
        d4 = feed.pushToOthersFeed(userId, orgId, item["meta"]["uuid"], itemId, itemId,
                    _acl, responseType, itemType, userId, promoteActor=False)

        d5 = utils.updateDisplayNameIndex(userId, [groupId],
                                          userInfo['basic']['name'], None)

        deferreds = [d1, d2, d3, d4, d5]
        yield defer.DeferredList(deferreds)


    @defer.inlineCallbacks
    def _cancelGroupInvitation(self, request):
        myId = request.getSession(IAuthInfo).username
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        cols = yield db.get_slice(myId, "pendingConnections", ["GI:%s"%(groupId)])
        if cols:
            yield self._removeFromPending(groupId, myId)
            args = {"groupId": groupId}
            args["entities"] = {groupId: group}
            args["myGroups"] = []
            args["groupFollowers"] = {groupId:[]}
            args["pendingConnections"] = []
            args['myId'] = myId
            yield renderScriptBlock(request, "group-feed.mako", "group_actions",
                                    False, "#group-actions-%s" %(groupId),
                                    "set", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _subscribe(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        orgId = args["orgId"]
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group", ["admins"])
        access = group["basic"]["access"]
        myGroups = []
        pendingRequests = {}
        groupFollowers = {groupId:[]}
        _pg = utils.getRequestArg(request, '_pg')

        cols = yield db.get_slice(groupId, "blockedUsers", [myId])
        if cols:
            raise errors.PermissionDenied(_("You are banned from joining this group."))

        args['entities'] = {groupId: group}
        colname = "%s:%s" %(group['basic']['name'].lower(), groupId)
        try:
            cols = yield db.get(myId, "entityGroupsMap", colname)
        except ttypes.NotFoundException:
            if access == "open":
                yield self._addMember(request, groupId, myId, orgId, group)
                myGroups.append(groupId)
                groupFollowers[groupId].append(myId)
                yield self._removeFromPending(groupId, myId)
                args["isMember"] = True
            else:
                # Add to pending connections
                yield db.insert(myId, "pendingConnections", '', "GO:%s" %(groupId))
                yield db.insert(groupId, "pendingConnections", '', "GI:%s"%(myId))

                yield self._notify(groupId, myId)
                pendingRequests["GO:%s"%(groupId)] = myId

                entities = yield db.multiget_slice(group["admins"], "entities", ["basic"])
                entities = utils.multiSuperColumnsToDict(entities)
                entities.update({groupId: group, orgId: args["org"], myId: args["me"]})
                data = {"entities": entities , "groupName": group['basic']['name']}
                yield notifications.notify(group["admins"], ":GR", myId, **data)

            args["pendingConnections"] = pendingRequests
            args["groupFollowers"] = groupFollowers
            args["groupId"] = groupId
            args["myGroups"] = myGroups

            if script:
                handlers = {}
                if access == 'open' and _pg == '/group':
                    onload = """
                                 $('#group_add_invitee').autocomplete({
                                    source: '/auto/users',
                                   minLength: 2,
                                   select: function( event, ui ) {
                                       $('#group_invitee').attr('value', ui.item.uid)
                                   }
                                  });
                                 """
                    yield renderScriptBlock(request, "group-feed.mako", "groupLinks",
                                            landing, "#group-links", "set",
                                            handlers={"onload":onload}, **args)

                    onload = "$('#sharebar-attach-fileshare,"\
                                "#sharebar-attach-file-input,"\
                                "#sharebar-submit').removeAttr('disabled');"
                    onload += "$('#group-share-block').removeClass('disabled');"
                    onload += "$('#group-links').show();"
                    handlers = {'onload': onload}

                yield renderScriptBlock(request, "group-feed.mako", "group_actions",
                                        landing, "#group-actions-%s" %(groupId),
                                        "set", handlers = handlers, **args)
                if access == 'open' and _pg == '/group':
                    feedItems = yield feed.getFeedItems(request, feedId=groupId)
                    args.update(feedItems)
                    onload = "(function(obj){$$.convs.load(obj);})(this);"
                    yield renderScriptBlock(request, "group-feed.mako", "feed",
                                            landing, "#user-feed", "set", True,
                                            handlers={"onload": onload}, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _approve(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myId in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            try:
                yield db.get(groupId, "pendingConnections", "GI:%s"%(userId))
                d1 = self._removeFromPending(groupId, userId)
                d2 = self._addMember(request, groupId, userId, orgId, group)
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
        myId = request.getSession(IAuthInfo).username
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myId in group["admins"]:
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
        myId = request.getSession(IAuthInfo).username
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myId in group["admins"]:
            userId, user = yield utils.getValidEntityId(request, "uid", "user")
            if myId == userId and myId in group["admins"]:
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
        myId = request.getSession(IAuthInfo).username
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        if myId in group["admins"]:
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
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        landing = not self._ajax
        _pg = utils.getRequestArg(request, '_pg')

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
        args = {"groupId": groupId}
        args["entities"] = {groupId: group}
        args["myGroups"] = []
        args["groupFollowers"] = {groupId:[]}
        args["pendingConnections"] = []
        me = yield db.get_slice(myId, "entities", ['basic'])
        me = utils.supercolumnsToDict(me)
        args["me"] = me
        args['myId'] = myId

        itemId = utils.getUniqueKey()
        acl = {"accept":{"groups":[groupId]}}
        _acl = pickle.dumps(acl)
        item, attachments = yield utils.createNewItem(request, itemType, myId,
                                                      orgId, acl, "groupLeave")
        item["meta"]["target"] = groupId

        d1 = db.remove(groupId, "followers", myId)
        d2 = db.remove(myId, "entityGroupsMap", colname)
        d3 = db.batch_insert(itemId, 'items', item)
        d4 = db.remove(groupId, "groupMembers", myId)

        d5 = feed.pushToOthersFeed(myId, orgId, item["meta"]["uuid"], itemId, itemId,
                        _acl, responseType, itemType, myId, promoteActor=False)
        d6 = renderScriptBlock(request, "group-feed.mako", "group_actions",
                               landing, "#group-actions-%s" %(groupId),
                               "set", **args)

        d7 = utils.updateDisplayNameIndex(myId, [groupId], None,
                                          args['me']['basic']['name'])
        deferreds = [d1, d2, d3, d4, d5, d6, d7]
        onload = "(function(obj){$$.convs.load(obj);})(this);"
        onload += "$('#sharebar-attach-fileshare, #sharebar-attach-file-input').attr('disabled', 'disabled');"
        onload += "$('#sharebar-submit').attr('disabled', 'disabled');"
        onload += "$('#group-share-block').addClass('disabled');"
        onload += "$('#group-links').hide();"
        args["isMember"] = False
        if _pg == '/group':
            d8 = renderScriptBlock(request, "group-feed.mako", "feed", landing,
                                    "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)
            deferreds.append(d8)

        yield defer.DeferredList(deferreds)

    @profile
    @defer.inlineCallbacks
    def _remove(self, request):
        """
            Method to remove an user from a group.
            Note: only a group-administrator can remove a user from the group.
        """
        myId = request.getSession(IAuthInfo).username
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                        columns=['admins'])
        if myId not in group['admins']:
            raise errors.InvalidRequest('Access Denied')

        userId, user = yield utils.getValidEntityId(request, 'uid', 'user')
        if len(group.get('admins', [])) == 1 and myId == userId:
            raise errors.InvalidRequest(_("You are currently the only administrator of this group"))

        try:
            cols = yield db.get(groupId, "groupMembers", userId)
            itemId = cols.column.value
            groupName= group['basic']['name']
            username = user['basic']['name']
            colName = '%s:%s' %(groupName.lower(), groupId)
            d1 = db.remove(itemId, "items")
            d2 = db.remove(groupId, "followers", userId)

            d3 = db.remove(userId, "entityGroupsMap", colName)
            d4 = db.remove(groupId, "groupMembers", userId)
            d5 = utils.updateDisplayNameIndex(userId, [groupId], '', username)

            d6 = renderScriptBlock(request, "groups.mako",
                                    "groupRequestActions", False,
                                    '#group-request-actions-%s-%s' %(userId, groupId),
                                    "set", args=[groupId, userId, "removed"])
            deferreds = [d1, d2, d3, d4, d5, d6]
            if userId in group['admins']:
                d7 = db.remove(groupId, 'entities', userId, 'admins')
                d8 = db.remove(userId, 'entities', groupId, 'adminOfGroups')
                deferreds.extend([d7, d8])

            #XXX: remove item from feed?
            yield defer.DeferredList(deferreds)
            ###XXX: if one of the admins is removed from the group,
            ### remove the user from group["admins"]

            request.write("$$.alerts.info('%s is removed from %s');" %(user['basic']['name'], group['basic']['name']))

        except ttypes.NotFoundException:
            pass

    @defer.inlineCallbacks
    def _makeAdmin(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                        columns=['admins'])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")
        if myId not in group['admins']:
            raise errors.InvalidRequest(_('You are not an administrator of the group'))

        cols = yield db.get_slice(groupId, "groupMembers", [userId])
        if not cols:
            raise errors.InvalidRequest(_('Only group members can become adminstrators'))

        if userId in group['admins']:
            defer.returnValue(None)

        yield db.insert(groupId, "entities", '', userId, 'admins')
        yield db.insert(userId, "entities", group['basic']['name'], groupId, "adminOfGroups")
        group['admins'] = {userId:''}
        args = {'entities': {groupId: group}}

        itemType = "activity"
        responseType = "I"
        acl = {"accept":{"groups":[groupId]}}
        _acl = pickle.dumps(acl)

        itemId = utils.getUniqueKey()
        item, attachments = yield utils.createNewItem(request, "activity",
                                                      userId, orgId, acl,
                                                      "groupAdmin")
        item["meta"]["target"] = groupId

        d1 = db.batch_insert(itemId, 'items', item)
        d2 = feed.pushToFeed(groupId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)
        d3 = feed.pushToOthersFeed(userId, orgId, item["meta"]["uuid"], itemId, itemId,
                    _acl, responseType, itemType, userId, promoteActor=False)

        yield renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' %(userId, groupId),
                                "set", args=[groupId, userId, "show_manage"], **args)
        yield defer.DeferredList([d1, d2, d3])

    @defer.inlineCallbacks
    def _removeAdmin(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                        columns=['admins'])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")
        if myId not in group['admins']:
            raise errors.InvalidRequest(_('You are not an administrator of the group'))
        if myId == userId and len(group['admins']) == 1:
            raise errors.InvalidRequest(_('You are currently the only administrator of this group'))

        cols = yield db.get_slice(groupId, "groupMembers", [userId])
        if not cols:
            raise errors.InvalidRequest(_("User is not a member of the group"))

        if userId not in group['admins']:
            raise errors.InvalidRequest(_('User is not administrator of the group'))

        yield db.remove(groupId, "entities", userId, "admins")
        yield db.remove(userId, "entities", groupId, "adminOfGroups")

        del group['admins'][userId]
        args = {'entities': {groupId: group}}
        if userId != myId:
            yield renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                    False, '#group-request-actions-%s-%s' %(userId, groupId),
                                    "set", args=[groupId, userId, "show_manage"], **args)
        else:
            handlers = {'onload':"$$.alerts.info('You are not admin of this group anymore.');"}
            args['groupId'] = groupId
            request.write("$$.fetchUri('/groups/members?id=%s');"%(groupId))
            yield renderScriptBlock(request, "group-settings.mako", "nav_menu",
                                    False, "#nav-menu", "set", True,
                                    handlers=handlers, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _create(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        name = utils.getRequestArg(request, "name")
        description = utils.getRequestArg(request, "desc")
        access = utils.getRequestArg(request, "access") or "open"
        dp = utils.getRequestArg(request, "dp", sanitize=False)

        if not name:
            request.write("<script> parent.$$.alerts.error('Group name is a required field'); </script>")
            raise errors.MissingParams([_("Group name")])

        cols = yield db.get_slice(orgId, "entityGroupsMap", start=name.lower(), count=2)
        for col in cols:
            if col.column.name.split(':')[0] == name.lower():
                request.write("<script> parent.$$.alerts.error('Group with same name already exists.'); </script>")
                raise errors.InvalidGroupName(name)

        groupId = utils.getUniqueKey()
        meta = {"name":name,
                "type":"group",
                "access":access,
                "org":orgId}
        admins = {myId:''}
        if description:
            meta["desc"] = description

        if dp:
            avatar = yield saveAvatarItem(groupId, orgId, dp)
            meta["avatar"] = avatar

        yield db.batch_insert(groupId, "entities", {"basic": meta,
                                                    "admins": admins})
        colname = "%s:%s" %(meta['name'].lower(), groupId)
        yield db.insert(myId, "entities", name, groupId, 'adminOfGroups')
        yield db.insert(orgId, "entityGroupsMap", '', colname)
        yield self._addMember(request, groupId, myId, orgId, {"basic":meta})

        response = """
                    <script>
                        parent.$$.alerts.info('%s');
                        parent.$.get('/ajax/notifications/new');
                        parent.$$.fetchUri('/groups');
                        parent.$$.dialog.close('addgroup-dlg', true);
                    </script>
                   """ %(_("Group Created"))
        request.write(response)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderCreate(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        args["menuId"] = "groups"

        if script and landing:
            yield render(request, "groups.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "groups.mako", "createGroup",
                                    landing, "#addgroup-dlg", "set", **args)


    @defer.inlineCallbacks
    def _getPendingGroupRequests(self, request):
        myId = request.getSession(IAuthInfo).username
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
    def _getGroupInvitations(self, request):
        myId = request.getSession(IAuthInfo).username

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
        pendingConnections = utils.columnsToDict(cols)
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

        defer.returnValue((groupIds, entities, prevPageStart, nextPageStart, pendingConnections))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listGroups(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args["orgId"]

        viewType = utils.getRequestArg(request, 'type') or 'myGroups'
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)

        viewTypes = ['myGroups', 'allGroups', 'adminGroups', 'pendingRequests', 'invitations']
        viewType = 'myGroups' if viewType not in viewTypes else viewType

        args["menuId"] = "groups"
        args['viewType']  = viewType
        alert_mesg = ''

        cols = yield db.get_slice(myId, "entities", super_column='adminOfGroups')
        managedGroupIds = [col.column.name for col in cols]
        ##TODO: can we use getLatestCounts instead of fetching pendingConnections?
        cols = yield db.multiget_slice(managedGroupIds, "pendingConnections", count=1)
        cols = utils.multiColumnsToDict(cols)

        showPendingRequestsTab = sum([len(cols[groupId]) for groupId in cols]) > 0
        args["showPendingRequestsTab"] = showPendingRequestsTab


        if viewType == 'pendingRequests' and not showPendingRequestsTab:
            viewType = 'myGroups'
            args["viewType"] = viewType

        cols = yield db.get_slice(myId, "pendingConnections", start="GI:", count=1)
        args["showInvitationsTab"] = bool(len([col for col in cols if col.column.name.startswith('GI:')]))

        if viewType == 'invitations' and not args["showInvitationsTab"]:
            viewType = 'myGroups'
            args['viewType'] = viewType


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
                columns = reduce(lambda x,y: x+y, [["GO:%s"%(x), "GI:%s"%(x)] for x in toFetchGroups])
                cols = yield db.get_slice(myId, 'pendingConnections', columns)
                pendingConnections = utils.columnsToDict(cols)
            args["entities"] = groups
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
            args['tab'] = 'pending'
        elif viewType == 'invitations':
            groupIds, entities, prevPageStart, nextPageStart, pendingConnections = yield self._getGroupInvitations(request)
            args["groupIds"] = groupIds
            args["entities"] = entities
            args["prevPageStart"] = prevPageStart
            args["nextPageStart"] = nextPageStart
            args["pendingConnections"] = pendingConnections
            args["myGroups"] = []
            args["groupFollowers"] = dict([(groupId, []) for groupId in groupIds])

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "viewOptions",
                                    landing, "#groups-view", "set", args=[viewType],
                                    showPendingRequestsTab=showPendingRequestsTab,
                                    showInvitationsTab = args['showInvitationsTab'],
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
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group", columns=['admins'])
        start = utils.getRequestArg(request, 'start') or ''

        cols = yield db.get_slice(groupId, "groupMembers", [myId])
        if not cols:
            raise errors.InvalidRequest(_("Access Denied"))

        fromFetchMore = ((not landing) and (not appchange) and start)
        args["menuId"] = "members"
        args["groupId"] = groupId
        args["entities"] = {groupId: group}
        args["tab"]= 'manage' if myId in group['admins'] else ''

        if script and landing:
            yield render(request, "group-settings.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users, relation, userIds, blockedUsers, nextPageStart,\
            prevPageStart = yield people.getPeople(myId, groupId,
                                                   args['orgId'], start=start)
        args["relations"] = relation
        args["entities"] = users
        args["userIds"] = userIds
        args["blockedUsers"] = blockedUsers
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["heading"] = group['basic']['name']
        args["entities"].update({groupId: group})

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "displayUsers",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "paging",
                                landing, "#groups-paging", "set", **args)

    @defer.inlineCallbacks
    @dump_args
    def _listBannedUsers(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group", columns=['admins'])
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        nextPageStart = ''
        prevPageStart = ''

        args["myId"] = myId
        args["menuId"] = "banned"
        args["groupId"] = groupId
        args["entities"] = {groupId: group}
        args["heading"] = group['basic']['name']

        if script and landing:
            yield render(request, "group-settings.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        toFetchCount = PEOPLE_PER_PAGE + 1
        cols = yield db.get_slice(groupId, "blockedUsers", start=start, count=toFetchCount)
        blockedUsers = [col.column.name for col in cols]

        if start:
            prevCols = yield db.get_slice(groupId, "blockedUsers", start=start, reverse=True, count=toFetchCount)
            if len(prevCols) > 1:
                prevPageStart = utils.encodeKey(prevCols[-1].column.name)

        if len(blockedUsers) == toFetchCount:
            nextPageStart = utils.encodeKey(blockedUsers[-1])
            blockedUsers  = blockedUsers[:PEOPLE_PER_PAGE]

        entities = yield db.multiget_slice(blockedUsers, "entities", ["basic"]) if blockedUsers else {}
        entities = utils.multiSuperColumnsToDict(entities)
        entities[groupId] = group

        args["entities"] = entities
        args["userIds"] = blockedUsers
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["tab"] = "banned"

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "displayUsers",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "bannedUsersPaging",
                                    landing, "#groups-paging", "set", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listPendingSubscriptions(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        start = utils.getRequestArg(request, 'start') or 'GI'
        count = PEOPLE_PER_PAGE
        toFetchCount = count+1
        nextPageStart = None
        prevPageStart = None

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        args["menuId"] = "pending"
        args["groupId"] = groupId
        args["entities"] = {groupId: group}
        args["heading"] = group['basic']['name']

        if script and landing:
            yield render(request, "group-settings.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if myId in group["admins"]:
            #or myId in moderators #if i am moderator
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

        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["entities"][groupId] = group
        args["tab"] = 'pending'

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "displayUsers",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, 'groups.mako', "pendingRequestsPaging",
                                    landing, "#groups-paging", "set", **args)



    @defer.inlineCallbacks
    def _invite(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
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
        #ignore the request if user is already a member or if the request is pending
        try:
            yield db.get(groupId, "groupMembers", userId)
        except ttypes.NotFoundException:
            try:
                yield db.get(userId, "pendingConnections", "GO:%s"%(groupId))
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
            elif request.postpath[0] == 'banned':
                d = self._listBannedUsers(request)

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
            elif action == 'cancel':
                d = self._cancelGroupInvitation(request)
            elif action == 'create':
                d = self._create(request)
            elif action == 'remove':
                d = self._remove(request)
            elif action == 'makeadmin':
                d = self._makeAdmin(request)
            elif action == 'removeadmin':
                d = self._removeAdmin(request)

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


class GroupFeedResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _feed(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        itemType = utils.getRequestArg(request, 'type')
        groupId, group = yield utils.getValidEntityId(request, 'id', 'group', columns=["admins"])
        start = utils.getRequestArg(request, "start") or ''

        landing = not self._ajax
        #if user dont belong to this group show "Join Group" message
        isMember = yield db.get_count(groupId, "groupMembers", start=myId, finish=myId)
        isFollower = yield db.get_count(groupId, "followers", start=myId, finish=myId)
        columns = ["GI:%s" %(groupId), "GO:%s" %(groupId)]
        pendingConnections = yield db.get_slice(myId, "pendingConnections", ["GI:%s"%(groupId),"GO:%s"%(groupId)])
        pendingConnections = utils.columnsToDict(pendingConnections)

        args["menuId"] = "groups"
        args["groupId"] = groupId
        args["isMember"] = isMember
        args['itemType'] = itemType
        args["group"] = group
        args["entities"]= {groupId:group}

        ##XXX: following should not be static
        args["pendingConnections"] = pendingConnections
        args["myGroups"] = [groupId] if isMember else []
        args["groupFollowers"] = {groupId:[myId]} if isFollower else {groupId:[]}

        if script and landing:
            yield render(request, "group-feed.mako", **args)
        elif script and appchange:
            yield renderScriptBlock(request, "group-feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
            name = group['basic']['name']
            onload = "$$.acl.switchACL('sharebar-acl', 'group', '%s', '%s');" % (groupId, name.replace("'", "\\'"))
            onload += "$$.files.init('sharebar-attach');"
            onload += "$('#sharebar-acl-button').attr('disabled', 'disabled');"
            if not isMember:
                onload += "$('#sharebar-attach-fileshare').attr('disabled', 'disabled');"
                onload += "$('#sharebar-attach-file-input').attr('disabled', 'disabled');"
                onload += "$('#sharebar-submit').attr('disabled', 'disabled');"
                onload += "$('#group-share-block').addClass('disabled');"

            yield renderScriptBlock(request, "group-feed.mako", "summary",
                                    landing, "#group-summary", "set", **args)
            yield renderScriptBlock(request, "feed.mako", "share_block",
                                    landing,  "#group-share-block", "set",
                                    handlers={"onload": onload}, **args)
            yield self._renderShareBlock(request, "status")

        if isMember:
            if itemType and itemType in plugins and plugins[itemType].hasIndex:
                feedItems = yield feed._feedFilter(request, groupId, itemType, start)
            else:
                feedItems = yield feed.getFeedItems(request, feedId=groupId, start=start)
            args.update(feedItems)
        else:
            args["conversations"]=[]

        admins = yield db.multiget_slice(group["admins"], 'entities', ["basic"])
        admins = utils.multiSuperColumnsToDict(admins)
        for admin in admins:
            if admin not in args["entities"]:
                args["entities"][admin] = admins[admin]
        #update overrides the group-info also
        args["entities"][groupId]  = group

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            yield renderScriptBlock(request, "group-feed.mako", "feed", landing,
                                    "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)
            if isMember:
                onload = """
                         $('#group_add_invitee').autocomplete({
                               source: '/auto/users',
                               minLength: 2,
                               select: function( event, ui ) {
                                   $('#group_invitee').attr('value', ui.item.uid)
                               }
                          });
                         """
                yield renderScriptBlock(request, "group-feed.mako", "groupLinks",
                                        landing, "#group-links", "set",
                                        handlers={"onload":onload}, **args)
            yield renderScriptBlock(request, "group-feed.mako", "groupAdmins",
                                    landing, "#group-admins", "set", True, **args)
        else:
            yield render(request, "group-feed.mako", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    # The client has scripts and this is an ajax request
    @defer.inlineCallbacks
    def _renderMore(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        myId = request.getSession(IAuthInfo).username

        entityId = utils.getRequestArg(request, "id")
        start = utils.getRequestArg(request, "start") or ""
        itemType = utils.getRequestArg(request, 'type')
        groupId, group = yield utils.getValidEntityId(request, 'id', 'group', ["admins"])
        isMember = yield db.get_count(groupId, "groupMembers", start=myId, finish=myId)
        if isMember:
            if itemType and itemType in plugins and plugins[itemType].hasIndex:
                feedItems = yield feed._feedFilter(request, entityId, itemType, start)
            else:
                feedItems = yield feed.getFeedItems(request, feedId=entityId, start=start)
            args.update(feedItems)
        else:
            args["conversations"]=[]
            args["entities"] = {}
        args['itemType'] = itemType
        args["isMember"] = isMember
        args["groupId"] = groupId
        args["entities"][groupId] = group

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        yield renderScriptBlock(request, "group-feed.mako", "feed", False,
                                "#next-load-wrapper", "replace", True,
                                handlers={"onload": onload}, **args)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._feed(request)
        elif segmentCount == 1 and request.postpath[0] == 'more':
            d = self._renderMore(request)
        return self._epilogue(request, d)


class GroupSettingsResource(base.BaseResource):

    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderEditGroup(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])

        args["menuId"] = "settings"
        args["groupId"] = groupId
        args["entities"] = {groupId:group}

        if myId not in group['admins']:
            raise errors.PermissionDenied('You should be an administrator to edit group meta data')

        if script and landing:
            yield render(request, "group-settings.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
            handlers = {}
            handlers["onload"] = """$$.ui.bindFormSubmit('#group-form');"""
            yield renderScriptBlock(request, "group-settings.mako", "edit_group",
                                    landing, "#center-content", "set", True,
                                    handlers=handlers, **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _edit(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        if myId not in group['admins']:
            raise errors.PermissionDenied('You should be an administrator to edit group meta data')
        name = utils.getRequestArg(request, 'name')
        desc = utils.getRequestArg(request, 'desc')
        access = utils.getRequestArg(request, 'access') or 'open'
        dp = utils.getRequestArg(request, "dp", sanitize=False) or ''

        # No two groups should have same name.
        if name:
            start = name.lower() + ':'
            cols = yield db.get_slice(orgId, "entityGroupsMap", start=start, count=1)
            for col in cols:
                name_, groupId_ = col.column.name.split(':')
                if name_ == name.lower() and groupId_ != groupId:
                    request.write("<script> parent.$$.alerts.error('Group with same name already exists.'); </script>")
                    raise errors.InvalidGroupName(name)

        meta = {'basic':{}}
        if name and name != group['basic']['name']:
            meta['basic']['name'] = name
        if desc and desc != group['basic'].get('desc', ''):
            meta['basic']['desc'] = desc
        if access in ['closed', 'open'] and access != group['basic']['access']:
            meta['basic']['access'] = access
        if dp:
            avatar = yield saveAvatarItem(groupId, orgId, dp)
            meta['basic']['avatar'] = avatar
        if name and name!=group["basic"]["name"]:
            members = yield db.get_slice(groupId, "groupMembers")
            members = utils.columnsToDict(members).keys()
            entities = members + [orgId]
            oldColName = "%s:%s"%(group["basic"]["name"].lower(), groupId)
            colname = '%s:%s' %(name.lower(), groupId)
            mutations = {}
            for entity in entities:
                mutations[entity] = {'entityGroupsMap':{colname:'', oldColName:None}}
            #XXX:notify group-members about the change in name
            yield db.batch_mutate(mutations)

        if meta['basic']:
            yield db.batch_insert(groupId, 'entities', meta)
        if not desc and group['basic'].get('desc', ''):
            yield db.remove(groupId, "entities", 'desc', 'basic')
        if (not desc and group['basic'].get('desc', '')) or meta['basic']:
            request.write("<script>parent.$$.alerts.info('updated successful');</script>")


    def render_GET(self, request):
        segmentCount = len(request.postpath)

        d = None
        if segmentCount == 0:
            d = self._renderEditGroup(request)
        elif segmentCount == 1 and request.postpath[0] == 'edit':
            d = self._renderEditGroup(request)

        return self._epilogue(request, d)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1 and request.postpath[0] == 'edit':
            d = self._edit(request)
        return self._epilogue(request, d)
