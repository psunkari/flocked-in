from twisted.internet   import defer
from telephus.cassandra import ttypes
from formencode         import compound

from social             import base, db, utils, errors, _, plugins
from social             import template as t
from social.core        import Feed
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args
from social.validators  import Validate, SocialSchema, Entity, SocialString
from social.core        import Group

class EntityGroup(SocialSchema):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))


class GroupAdminAction(SocialSchema):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))
    uid = compound.Pipe(SocialString(if_missing=''),
                        Entity(entityType='user'))


class GroupInvite(SocialSchema):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))
    invitee = compound.Pipe(SocialString(if_missing=''),
                            Entity(entityType='user'))


class GroupFeed(SocialSchema):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))
    start = SocialString(if_missing='')
    type = SocialString(if_missing='')


class GroupMembers(SocialSchema):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))
    start = SocialString(if_missing='')


class CreateGroup(SocialSchema):
    name = SocialString()
    desc = SocialString(if_missing='')
    access = SocialString(if_missing='open')
    dp = SocialString(sanitize=False, if_missing='')


class UpdateGroup(CreateGroup):
    id = compound.Pipe(SocialString(if_missing=''),
                       Entity(entityType='group', columns=['admins']))


###############################################################################
###############################################################################

class GroupsResource(base.BaseResource):
    isLeaf = True
    _templates = ['group-feed.mako', 'groups.mako',
                  'group-settings.mako', 'feed.mako']

    @profile
    @Validate(EntityGroup)
    @defer.inlineCallbacks
    @dump_args
    def _follow(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        me = base.Entity(myId)
        group = data['id']
        followed = yield Group.follow(group, me)
        if followed:
            args = {"groupId": group.id, "myGroups": [group.id], "me": me,
                    "entities": {group.id: group}, "pendingConnections": {},
                    "groupFollowers": {group.id: [me.id]}}
            t.renderScriptBlock(request, "group-feed.mako", "group_actions",
                                False, "#group-actions-%s" % (group.id),
                                "set", **args)

    @profile
    @Validate(EntityGroup)
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        me = base.Entity(myId)
        group = data['id']
        unfollowed = yield Group.unfollow(group, me)
        if unfollowed:
            args = {"groupId": group.id, "myGroups": [group.id], "me": me,
                    "entities": {group.id: group}, "pendingConnections": {},
                    "groupFollowers": {group.id: []}}
            t.renderScriptBlock(request, "group-feed.mako", "group_actions",
                                False, "#group-actions-%s" % (group.id),
                                "set", **args)

    @Validate(EntityGroup)
    @defer.inlineCallbacks
    def _cancelGroupInvitation(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        group = data['id']
        me = base.Entity(myId)
        yield me.fetchData()
        cancelled = yield Group.cancelRequest(group, me)

        if cancelled:
            args = {"groupId": group.id, "entities": {group.id: group},
                    "myGroups": [], "groupFollowers": {group.id: []},
                    "pendingConnections": [], "me": me}
            t.renderScriptBlock(request, "group-feed.mako", "group_actions",
                                False, "#group-actions-%s" % (group.id),
                                "set", **args)

    @profile
    @Validate(EntityGroup)
    @defer.inlineCallbacks
    @dump_args
    def _subscribe(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        myGroups = []
        _pg = data['_pg']
        group = data['id']
        groupFollowers = {group.id: []}
        entities = base.EntitySet([myId, orgId])
        yield entities.fetchData()
        entities.update(group)
        args = {'entities': entities, "me": entities[myId]}

        isNewMember, pendingRequests = yield Group.subscribe(request, group, entities[myId], entities[orgId])
        if isNewMember or pendingRequests:
            if isNewMember:
                myGroups.append(group.id)
                groupFollowers[group.id].append(myId)
            args["isMember"] = isNewMember
            args["pendingConnections"] = pendingRequests
            args["groupFollowers"] = groupFollowers
            args["groupId"] = group.id
            args["myGroups"] = myGroups

            handlers = {}
            if group.basic['access'] == 'open' and _pg == '/group':
                onload = """
                             $('#group_add_invitee').autocomplete({
                                source: '/auto/users',
                               minLength: 2,
                               select: function( event, ui ) {
                                   $('#group_invitee').attr('value', ui.item.uid)
                               }
                              });
                             """
                t.renderScriptBlock(request, "group-feed.mako", "groupLinks",
                                    False, "#group-links", "set",
                                    handlers={"onload": onload}, **args)

                onload = "$('#sharebar-attach-fileshare,"\
                            "#sharebar-attach-file-input,"\
                            "#sharebar-submit').removeAttr('disabled');"
                onload += "$('#group-share-block').removeClass('disabled');"
                onload += "$('#group-links').show();"
                handlers = {'onload': onload}

            t.renderScriptBlock(request, "group-feed.mako", "group_actions",
                                False, "#group-actions-%s" % (group.id),
                                "set", handlers=handlers, **args)
            if group.basic['access'] == 'open' and _pg == '/group':
                feedItems = yield Feed.get(request.getSession(IAuthInfo), feedId=group.id)
                args.update(feedItems)
                onload = "(function(obj){$$.convs.load(obj);})(this);"
                t.renderScriptBlock(request, "group-feed.mako", "feed",
                                    False, "#user-feed", "set", True,
                                    handlers={"onload": onload}, **args)

    @profile
    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    @dump_args
    def _approve(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        group = data['id']
        user = data['uid']
        me = base.Entity(myId)
        yield me.fetchData()
        approved = yield Group.approveRequest(request, group, user, me)
        if approved:
            t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' % (user.id, group.id),
                                "set", args=[group.id, user.id, "accept"])

    @profile
    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    @dump_args
    def _reject(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        group = data['id']
        user = data['uid']
        me = base.Entity(myId)
        render = yield Group.rejectRequest(group, user, me)
        if render:
            t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' % (user.id, group.id),
                                "set", args=[group.id, user.id, "reject"])

    @profile
    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    @dump_args
    def _block(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        group = data['id']
        user = data['uid']
        me = base.Entity(myId)
        blocked = yield Group.block(group, user, me)
        if blocked:
            t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' % (user.id, group.id),
                                "set", args=[group.id, user.id, "block"])

    @profile
    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    @dump_args
    def _unblock(self, request, data=None):
        myId = request.getSession(IAuthInfo).username
        group = data['id']
        user = data['uid']
        me = base.Entity(myId)

        yield Group.unblock(group, user, me)
        t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                            False, '#group-request-actions-%s-%s' % (user.id, group.id),
                            "set", args=[group.id, user.id, "unblock"])

    @profile
    @Validate(EntityGroup)
    @defer.inlineCallbacks
    @dump_args
    def _unsubscribe(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username

        group = data['id']
        _pg = data['_pg']
        me = base.Entity(myId)
        yield me.fetchData(['basic'])

        yield Group.unsubscribe(request, group, me)
        args = {"groupId": group.id, "me": me, "myGroups": [],
                "entities": {group.id: group}, "groupFollowers": {group.id: []},
                "pendingConnections": [], "isMember": False}
        t.renderScriptBlock(request, "group-feed.mako", "group_actions", False,
                            "#group-actions-%s" % (group.id), "set", **args)

        if _pg == '/group':
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            onload += "$('#sharebar-attach-fileshare, #sharebar-attach-file-input').attr('disabled', 'disabled');"
            onload += "$('#sharebar-submit').attr('disabled', 'disabled');"
            onload += "$('#group-share-block').addClass('disabled');"
            onload += "$('#group-links').hide();"
            t.renderScriptBlock(request, "group-feed.mako", "feed",
                                False, "#user-feed", "set", True,
                                handlers={"onload": onload}, **args)

    @profile
    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    def _remove(self, request, data=None):
        """
            Method to remove an user from a group.
            Note: only a group-administrator can remove a user from the group.
        """
        myId = request.getSession(IAuthInfo).username

        group = data['id']
        user = data['uid']
        me = base.Entity(myId)

        removed = yield Group.removeUser(group, user, me)
        if removed:
            t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' % (user.id, group.id),
                                "set", args=[group.id, user.id, "removed"])
            request.write("$$.alerts.info('%s is removed from %s');" % (user.basic['name'], group.basic['name']))

    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    def _makeAdmin(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username

        group = data['id']
        user = data['uid']
        me = base.Entity(myId)

        yield Group.makeAdmin(request, group, user, me)
        group.admins[user.id] = ''
        args = {'entities': {group.id: group}}

        t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                            False, '#group-request-actions-%s-%s' % (user.id, group.id),
                            "set", args=[group.id, user.id, "show_manage"], **args)

    @Validate(GroupAdminAction)
    @defer.inlineCallbacks
    def _removeAdmin(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username

        group = data['id']
        user = data['uid']
        me = base.Entity(myId)
        yield Group.removeAdmin(group, user, me)

        del group.admins[user.id]
        args = {'entities': {group.id: group}}
        if user.id != me.id:
            t.renderScriptBlock(request, "groups.mako", "groupRequestActions",
                                False, '#group-request-actions-%s-%s' % (user.id, group.id),
                                "set", args=[group.id, user.id, "show_manage"], **args)
        else:
            handlers = {'onload': "$$.alerts.info('You are not admin of this group anymore.');"}
            args['groupId'] = group.id
            request.write("$$.fetchUri('/groups/members?id=%s');" % (group.id))
            t.renderScriptBlock(request, "group-settings.mako", "nav_menu",
                                False, "#nav-menu", "set", True,
                                handlers=handlers, **args)

    @profile
    @Validate(CreateGroup)
    @defer.inlineCallbacks
    @dump_args
    def _create(self, request, data=None):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username

        name = data['name']
        description = data['desc']
        access = data['access']
        dp = data['dp']
        me = base.Entity(myId)
        yield me.fetchData()
        try:
            yield Group.create(request, me, name, access, description, dp)
        except errors.InvalidGroupName as e:
            request.write("<script> parent.$$.alerts.error('Group with same name already exists.'); </script>")
            raise e

        response = """
                    <script>
                        parent.$$.alerts.info('%s');
                        parent.$.get('/ajax/notifications/new');
                        parent.$$.fetchUri('/groups');
                        parent.$$.dialog.close('addgroup-dlg', true);
                    </script>
                   """ % (_("Group Created"))
        request.write(response)

    @profile
    @Validate(UpdateGroup)
    @defer.inlineCallbacks
    @dump_args
    def _edit(self, request, data=None):
        myId = request.getSession(IAuthInfo).username

        group = data['id']
        name = data['name']
        desc = data['desc']
        access = data['access']
        dp = data['dp']
        me = base.Entity(myId)
        yield me.fetchData()

        try:
            updated = yield Group.edit(me, group, name, access, desc, dp)
        except errors.InvalidGroupName as e:
            request.write("<script> parent.$$.alerts.error('Group with same name already exists.'); </script>")
            raise e

        if updated:
            request.write("<script>parent.$$.alerts.info('updated successful');</script>")

    @defer.inlineCallbacks
    @dump_args
    def _listGroups(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        me = args['me']

        viewType = utils.getRequestArg(request, 'type') or 'myGroups'
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)

        viewTypes = ['myGroups', 'allGroups', 'adminGroups', 'pendingRequests', 'invitations']
        viewType = 'myGroups' if viewType not in viewTypes else viewType

        args["menuId"] = "groups"
        args['viewType'] = viewType

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
            t.render(request, "groups.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "groups.mako", "layout",
                                landing, "#mainbar", "set", **args)

        if viewType not in ['pendingRequests', 'invitations']:
            if viewType == 'myGroups':
                data = yield Group.getGroups(me, me, start)
            elif viewType == 'allGroups':
                data = yield Group.getGroups(me, args['org'], start)
            else:
                data = yield Group.getManagedGroups(me, start)
            args.update(data)

        elif viewType == 'pendingRequests':
            data = yield Group.getGroupRequests(me, start)
            args.update(data)
            args['tab'] = 'pending'
        elif viewType == 'invitations':
            data = yield Group.getAllInvitations(me, start)
            args.update(data)

        if script:
            t.renderScriptBlock(request, "groups.mako", "titlebar",
                                landing, "#titlebar", "set", **args)
            t.renderScriptBlock(request, "groups.mako", "viewOptions",
                                landing, "#groups-view", "set", args=[viewType],
                                showPendingRequestsTab=showPendingRequestsTab,
                                showInvitationsTab=args['showInvitationsTab'],
                                groupRequestCount=groupRequestCount)
            if viewType == "pendingRequests":
                t.renderScriptBlock(request, "groups.mako", "allPendingRequests",
                                    landing, "#groups-wrapper", "set", **args)
            else:
                t.renderScriptBlock(request, "groups.mako", "listGroups",
                                    landing, "#groups-wrapper", "set", **args)
            t.renderScriptBlock(request, "groups.mako", "paging",
                                landing, "#groups-paging", "set", **args)

        if not script:
            t.render(request, "groups.mako", **args)

    @profile
    @Validate(GroupMembers)
    @defer.inlineCallbacks
    @dump_args
    def _listGroupMembers(self, request, data=None):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        me = args['me']

        group = data['id']
        start = data['start']

        groupMembers_d = Group.getMembers(group, me, start=start)
        args.update({"menuId": "members", "groupId": group.id,
                      "entities": {group.id: group}})
        args["tab"] = 'manage' if myId in group.admins else ''

        if script and landing:
            t.render(request, "group-settings.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        entities, relation, userIds, blockedUsers, \
            nextPageStart, prevPageStart = yield groupMembers_d

        #arg.update overwrites existing entities, so add group
        entities.update(group)
        args.update({"relations": relation, "entities": entities,
                     "userIds": userIds, "blockedUsers": blockedUsers,
                     "nextPageStart": nextPageStart,
                     "prevPageStart": prevPageStart,
                     "heading": group.basic['name']})

        if script:
            t.renderScriptBlock(request, "group-settings.mako", "titlebar",
                                landing, "#titlebar", "set", **args)
            t.renderScriptBlock(request, "group-settings.mako", "displayUsers",
                                landing, "#groups-wrapper", "set", **args)
            t.renderScriptBlock(request, "group-settings.mako", "paging",
                                landing, "#groups-paging", "set", **args)
        else:
            t.render(request, "group-settings.mako", **args)

    @Validate(GroupMembers)
    @defer.inlineCallbacks
    @dump_args
    def _listBannedUsers(self, request, data=None):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        me = args['me']

        group = data['id']
        start = data['start']
        start = utils.decodeKey(start)
        entities = base.EntitySet(group)

        args.update({"menuId": "banned", "groupId": group.id,
                     "entities": entities, "heading": group.basic['name']})

        if me.id not in group.admins:
            raise errors.InvalidRequest(_("Access Denied"))

        if script and landing:
            t.render(request, "group-settings.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "group-settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        data = yield Group.getBlockedMembers(group, me, start)
        print data.keys()
        args.update(data)
        args['entities'].update(group)
        args["tab"] = "banned"

        if script:
            t.renderScriptBlock(request, "group-settings.mako", "titlebar",
                                landing, "#titlebar", "set", **args)
            t.renderScriptBlock(request, "group-settings.mako", "displayUsers",
                                landing, "#groups-wrapper", "set", **args)
            t.renderScriptBlock(request, "group-settings.mako", "bannedUsersPaging",
                                landing, "#groups-paging", "set", **args)

    @profile
    @Validate(GroupMembers)
    @defer.inlineCallbacks
    @dump_args
    def _listPendingSubscriptions(self, request, data=None):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        me = args['me']

        group = data['id']
        start = data['start'] or 'GI'

        entities = base.EntitySet(group)

        args.update({"menuId": "pending", "groupId": group.id,
                     "entities": entities, "heading": group.basic['name']})

        if me.id not in group.admins:
            raise errors.InvalidRequest('Access Denied')
        if script and landing:
            t.render(request, "group-settings.mako", **args)
        if script and appchange:
            t.renderScriptBlock(request, "group-settings.mako", "layout",
                                landing, "#mainbar", "set", **args)

        data = yield Group.getPendingRequests(group, me, start)
        args.update(data)
        args["entities"].update(group)
        args["tab"] = 'pending'

        if script:
            t.renderScriptBlock(request, "groups.mako", "titlebar",
                                landing, "#titlebar", "set", **args)
            t.renderScriptBlock(request, "group-settings.mako", "displayUsers",
                                landing, "#groups-wrapper", "set", **args)
            t.renderScriptBlock(request, 'groups.mako', "pendingRequestsPaging",
                                landing, "#groups-paging", "set", **args)

    @Validate(GroupInvite)
    @defer.inlineCallbacks
    def _invite(self, request, data=None):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax

        group = data['id']
        user = data['invitee']
        me = args['me']
        args["groupId"] = group.id
        args["heading"] = group.basic["name"]

        if script and landing:
            t.render(request, "groups.mako", **args)
        if script and appchange:
            t.renderScriptBlock(request, "groups.mako", "layout",
                                landing, "#mainbar", "set", **args)
        try:
            yield Group.invite(group, me, user)
        except ttypes.NotFoundException:
            request.write('$$.alerts.error("You should be member of the group to Invite Others");')
        finally:
            request.write("""$("#group_add_invitee").attr("value", "");"""\
                          """$$.alerts.info("%s is invited to the %s");""" % (user.basic["name"], group.basic["name"]))

    def _renderCreate(self, request):
        t.renderScriptBlock(request, "groups.mako", "createGroup",
                            False, "#addgroup-dlg", "set")
        return True

    @profile
    @Validate(EntityGroup)
    @defer.inlineCallbacks
    @dump_args
    def _renderEditGroup(self, request, data=None):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax

        group = data['id']
        args["menuId"] = "settings"
        args["groupId"] = group.id
        args["entities"] = base.EntitySet(group)
        args["heading"] = group['basic']['name']

        if myId not in group.admins:
            raise errors.PermissionDenied('You should be an administrator to edit group meta data')

        if script and landing:
            t.render(request, "group-settings.mako", **args)
        if script and appchange:
            t.renderScriptBlock(request, "group-settings.mako", "layout",
                                landing, "#mainbar", "set", **args)
        if script:
            handlers = {}
            handlers["onload"] = """$$.ui.bindFormSubmit('#group-form');"""
            t.renderScriptBlock(request, "group-settings.mako", "edit_group",
                                landing, "#center-content", "set", True,
                                handlers=handlers, **args)
        else:
            t.render(request, "group-settings.mako", **args)

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
            elif request.postpath[0] == 'edit':
                d = self._renderEditGroup(request)

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
            elif action == 'remove':
                d = self._remove(request)
            elif action == 'makeadmin':
                d = self._makeAdmin(request)
            elif action == 'removeadmin':
                d = self._removeAdmin(request)
            elif action == 'create':
                d = self._create(request)
            elif action == 'edit':
                d = self._edit(request)

            def _updatePendingGroupRequestCount(ign):
                def _update_count(counts):
                    pendingRequestCount = counts['groups'] if counts.get('groups', 0) != 0 else ''
                    request.write("$('#pending-group-requests-count').html('%s');" % (pendingRequestCount))
                d01 = utils.render_LatestCounts(request, False, False)
                d01.addCallback(_update_count)
                return d01
            if action not in ["create", "edit"]:
                d.addCallback(_updatePendingGroupRequestCount)

        return self._epilogue(request, d)


class GroupFeedResource(base.BaseResource):
    isLeaf = True

    @profile
    @Validate(GroupFeed)
    @defer.inlineCallbacks
    @dump_args
    def _feed(self, request, data=None):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        group = data['id']
        start = data['start']
        itemType = data['type']

        #if user dont belong to this group show "Join Group" message
        isMember = yield db.get_count(group.id, "groupMembers", start=myId, finish=myId)
        isFollower = yield db.get_count(group.id, "followers", start=myId, finish=myId)
        columns = ["GI:%s" % (group.id), "GO:%s" % (group.id)]
        cols = yield db.get_slice(myId, "pendingConnections",  columns)
        pendingConnections = utils.columnsToDict(cols)

        args["menuId"] = "groups"
        args["groupId"] = group.id
        args["isMember"] = isMember
        args['itemType'] = itemType
        args["entities"] = base.EntitySet(group)

        ##XXX: following should not be static
        args["pendingConnections"] = pendingConnections
        args["myGroups"] = [group.id] if isMember else []
        args["groupFollowers"] = {group.id: [myId]} if isFollower else {group.id: []}

        if script and landing:
            t.render(request, "group-feed.mako", **args)
        elif script and appchange:
            t.renderScriptBlock(request, "group-feed.mako", "layout",
                                landing, "#mainbar", "set", **args)
        if script:
            name = group.basic['name']
            onload = "$$.acl.switchACL('sharebar-acl', 'group', '%s', '%s');" % (group.id, name.replace("'", "\\'"))
            onload += "$$.files.init('sharebar-attach');"
            onload += "$('#sharebar-acl-button').attr('disabled', 'disabled');"
            if not isMember:
                onload += "$('#sharebar-attach-fileshare').attr('disabled', 'disabled');"
                onload += "$('#sharebar-attach-file-input').attr('disabled', 'disabled');"
                onload += "$('#sharebar-submit').attr('disabled', 'disabled');"
                onload += "$('#group-share-block').addClass('disabled');"

            t.renderScriptBlock(request, "group-feed.mako", "summary",
                                landing, "#group-summary", "set", **args)
            t.renderScriptBlock(request, "feed.mako", "share_block",
                                landing,  "#group-share-block", "set",
                                handlers={"onload": onload}, **args)
            yield self._renderShareBlock(request, "status")

        if isMember:
            feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                       feedId=group.id, start=start,
                                       itemType=itemType)
            args.update(feedItems)
        else:
            args["conversations"] = []

        entities = base.EntitySet(group.admins.keys())
        yield entities.fetchData()
        for entityId in entities.keys():
            if entityId not in args['entities']:
                args['entities'][entityId] = entities[entityId]
        #group info fetched by feed may not have required info. overwrite it.
        args['entities'].update(group)

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            t.renderScriptBlock(request, "group-feed.mako", "feed", landing,
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
                          $('#feed-side-block-container').empty();
                         """
                t.renderScriptBlock(request, "group-feed.mako", "groupLinks",
                                    landing, "#group-links", "set",
                                    handlers={"onload": onload}, **args)

            t.renderScriptBlock(request, "group-feed.mako", "groupAdmins",
                                landing, "#group-admins", "set", True, **args)

            if isMember:
                for pluginType in plugins:
                    plugin = plugins[pluginType]
                    if hasattr(plugin, 'renderFeedSideBlock'):
                        yield plugins["event"].renderFeedSideBlock(request,
                                                        landing, group.id, args)

        else:
            t.render(request, "group-feed.mako", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    # The client has scripts and this is an ajax request
    @Validate(GroupFeed)
    @defer.inlineCallbacks
    def _renderMore(self, request, data=None):
        myId = request.getSession(IAuthInfo).username

        group = data['id']
        start = data['start']
        itemType = data['type']
        me = base.Entity(myId)
        me_d = me.fetchData()
        args = {'itemType': itemType, 'groupId': group.id, "me": me}

        isMember = yield db.get_count(group.id, "groupMembers", start=myId, finish=myId)
        if isMember:
            feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                       feedId=group.id, start=start,
                                       itemType=itemType)
            args.update(feedItems)
        else:
            args["conversations"] = []
            args["entities"] = {}
        yield me_d
        args["isMember"] = isMember
        args["entities"].update(group)
        args['entities'].update(me)

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        t.renderScriptBlock(request, "group-feed.mako", "feed", False,
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
