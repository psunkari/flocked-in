import json
import uuid
from twisted.web        import server
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes
try:
    import cPickle as pickle
except:
    import pickle


from social             import base, db, utils, errors, feed, people, _
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args
from social.profile     import saveAvatarItem


class GroupsResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _follow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        groupId, group = yield utils.getValidEntityId(request, "id", "group")

        try:
            cols = yield db.get(myKey, "entityGroupsMap", groupId)
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
            cols = yield db.get(myKey, "entityGroupsMap", groupId)
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
    def _addMember(self, request, groupId, userId, orgId):
        deferreds = []
        itemType = "activity"
        relation = Relation(userId, [])
        cols = yield db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)

        responseType = "I"
        acl = {"accept":{"groups":[groupId], "followers":[], "friends":[]}}
        _acl = pickle.dumps(acl)

        itemId = utils.getUniqueKey()
        item, attachments = yield utils.createNewItem(request, "activity", userId,
                                   acl, "groupJoin", orgId)
        item["meta"]["target"] = groupId

        d1 = db.insert(userId, "entityGroupsMap", "", groupId)
        d2 = db.insert(groupId, "followers", "", userId)
        d3 = db.insert(groupId, "groupMembers", itemId, userId)
        d4 = db.batch_insert(itemId, 'items', item)

        d5 = feed.pushToFeed(userId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)
        d6 = feed.pushToFeed(groupId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)

        d7 = feed.pushToOthersFeed(userId, item["meta"]["uuid"], itemId, itemId,
                                   _acl, responseType, itemType, userId)
        d8 = utils.updateDisplayNameIndex(userId, [groupId],
                                          userInfo['basic']['name'], None)
        deferreds = [d1, d2, d3, d4, d5, d6, d7, d8]
        yield defer.DeferredList(deferreds)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _subscribe(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args["orgKey"]
        groupId, group = yield utils.getValidEntityId(request, "id", "group")
        access = group["basic"]["access"]
        myGroups = []
        pendingRequests = {}
        groupFollowers = {groupId:[]}

        cols = yield db.get_slice(groupId, "bannedUsers", [myKey])
        if cols:
            raise errors.PermissionDenied(_("You are banned from joining the group by the administrator"))

        try:
            cols = yield db.get(myKey, "entityGroupsMap", groupId)
        except ttypes.NotFoundException:
            #add to pending connections
            if access == "public":
                yield self._addMember(request, groupId, myKey, myOrgId)
                myGroups.append(groupId)
                groupFollowers[groupId].append(myKey)
            else:
                yield db.insert(myKey, "pendingConnections", '0', groupId)
                yield db.insert(groupId, "pendingConnections", '1', myKey)
                #notify admin of the group
                cols = yield db.get_slice(groupId, "entities", ["admins"])
                admins = utils.supercolumnsToDict(cols)

                #XXX: notifications in new format
                timeUUID = uuid.uuid1().bytes
                yield db.insert(groupId, "latestNotifications", myKey, timeUUID, 'incomingGroupRequests')
                yield db.insert(myKey, "latestNotifications", groupId, timeUUID, 'outgoingGroupRequests')

                #for admin in admins["admins"]:
                #    commentOwner = myKey
                #    responseType = "G"
                #    value = ":".join([responseType, commentOwner, groupId, '', admin])
                #    yield db.insert(admin, "notifications", groupId, timeUUID)
                #    yield db.batch_insert(admin, "notificationItems", {groupId:{timeUUID:value}})

                pendingRequests[groupId]=myKey
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
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield db.get(groupId, "pendingConnections", userId)
                yield db.remove(groupId, "pendingConnections", userId)
                yield db.remove(userId, "pendingConnections", groupId)
                cols  = yield db.get_slice(groupId, "latestNotifications", ['incomingGroupRequests'])
                cols = utils.supercolumnsToDict(cols)
                for tuuid, key in cols['incomingGroupRequests'].items():
                    if key == userId:
                        yield db.remove(groupId, "latestNotifications", tuuid, 'incomingGroupRequests')
                        yield db.remove(userId, "latestNotifications", tuuid, 'outgoingGroupRequests')
                        break
                yield self._addMember(request, groupId, userId, myOrgId)
            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _reject(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield db.get(groupId, "pendingConnections", userId)
                yield db.remove(groupId, "pendingConnections", userId)
                yield db.remove(userId, "pendingConnections", groupId)
                cols  = yield db.get_slice(groupId, "latestNotifications", ['incomingGroupRequests'])
                cols = utils.supercolumnsToDict(cols)
                for tuuid, key in cols['incomingGroupRequests'].items():
                    if key == userId:
                        yield db.remove(groupId, "latestNotifications", tuuid, 'incomingGroupRequests')
                        yield db.remove(userId, "latestNotifications", tuuid, 'outgoingGroupRequests')
                        break
                # notify user that the moderator rejected.
            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _block(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey == userId and myKey in group["admins"]:
            raise errors.InvalidRequest(_("An administrator cannot ban himself/herself from the group"))

        if myKey in group["admins"]:
            # if the request is pending, remove the request
            yield db.remove(groupId, "pendingConnections", userId)
            yield db.remove(userId, "pendingConnections", groupId)
            cols  = yield db.get_slice(groupId, "latestNotifications", ['incomingGroupRequests'])
            cols = utils.supercolumnsToDict(cols)
            for tuuid, key in cols['incomingGroupRequests'].items():
                if key == userId:
                    yield db.remove(groupId, "latestNotifications", tuuid, 'incomingGroupRequests')
                    yield db.remove(userId, "latestNotifications", tuuid, 'outgoingGroupRequests')
                    break

            # if the users is already a member, remove the user from the group
            yield db.remove(groupId, "groupMembers", userId)
            yield db.remove(groupId, "followers", userId)
            yield db.remove(userId, "entityGroupsMap", groupId)

            yield db.insert(groupId, "bannedUsers", '', userId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unblock(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey in group["admins"]:
            # if the request is pending, remove the request
            yield db.remove(groupId, "bannedUsers", userId)
            log.msg("unblocked user %s from group %s"%(userId, groupId))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unsubscribe(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args["orgKey"]

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userGroup = yield db.get_slice(myId, "entityGroupsMap", [groupId])
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
        acl = {"accept":{"groups":[groupId], "followers":[], "friends":[]}}
        _acl = pickle.dumps(acl)
        item, attachments = yield utils.createNewItem(request, itemType, myId,
                                   acl, "groupLeave", orgId)
        item["meta"]["target"] = groupId

        d1 = db.remove(groupId, "followers", myId)
        d2 = db.remove(myId, "entityGroupsMap", groupId)
        d3 = db.batch_insert(itemId, 'items', item)
        d4 = db.remove(groupId, "groupMembers", myId)
        #d4 = db.insert(groupId, "groupMembers", itemId, myId)

        d5 = feed.pushToFeed(myId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, myId)

        d6 = feed.pushToOthersFeed(myId, item["meta"]["uuid"], itemId, itemId,
                                   _acl, responseType, itemType, myId)
        d7 =  renderScriptBlock(request, "groups.mako", "group_actions",
                                landing, "#group-actions-%s" %(groupId),
                                "set", **args)
        d8 = utils.updateDisplayNameIndex(myId, [groupId], None,
                                          args['me']['basic']['name'])

        yield defer.DeferredList([d1, d2, d3, d4, d5, d6, d7, d8])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _create(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]

        name = utils.getRequestArg(request, "name")
        description = utils.getRequestArg(request, "desc")
        access = utils.getRequestArg(request, "access") or "public"
        dp = utils.getRequestArg(request, "dp", sanitize=False)

        if not name:
            raise errors.MissingParams([_("Group name")])

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
        yield db.insert(myKey, "entities", '', groupId, 'adminOfGroups')
        yield db.insert(orgKey, "entityGroupsMap", '', groupId)
        yield self._addMember(request, groupId, myKey, orgKey)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderCreate(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgKey = args["orgKey"]
        args["menuId"] = "groups"

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
             yield renderScriptBlock(request, "groups.mako", "createGroup",
                                    landing, "#add-user-wrapper", "set", **args)
             request.write("$$.ui.bindFormSubmit('#group_form', function(){$('#add-user-wrapper').empty();$$.fetchUri('/groups');})");

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

        viewTypes = ['myGroups', 'allGroups', 'adminGroups']
        viewType = 'myGroups' if viewType not in viewTypes else viewType
        count = 110
        toFetchCount = count+1

        args["menuId"] = "groups"
        args['viewType']  = viewType
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
            groupIds = utils.columnsToDict(cols, ordered=True).keys()
            toFetchGroups.update(set(groupIds))
        elif viewType == 'adminGroups':
            cols = yield db.get_slice(myId, "entities", ['adminOfGroups'])
            groupIds = utils.supercolumnsToDict(cols, ordered=True)
            if groupIds:
                groupIds = groupIds['adminOfGroups'].keys()
                toFetchGroups.update(set(groupIds))


        cols = yield db.get_slice(myId, "entityGroupsMap",
                                  start=start, count=toFetchCount)
        myGroupsIds = utils.columnsToDict(cols, ordered=True).keys()

        if len(groupIds) > count:
            nextPageStart = utils.encodeKey(groupIds[-1])
            groupIds = groupIds[0:count]

        if start:
            cols = yield db.get_slice(entityId, 'entityGroupsMap', start=start,
                                      count=toFetchCount,  reverse=True)
            if len(cols) > 1:
                prevPageStart = utils.encodeKey(cols[-1].column.name)

        if toFetchGroups:
            groups = yield db.multiget_slice(toFetchGroups, "entities", ["basic"])
            groups = utils.multiSuperColumnsToDict(groups)
            groupFollowers = yield db.multiget_slice(toFetchGroups, "followers", names=[myId])
            groupFollowers = utils.multiColumnsToDict(groupFollowers)
            cols = yield db.get_slice(myId, 'pendingConnections', toFetchGroups)
            pendingConnections = dict((x.column.name, x.column.value) for x in cols)


        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        args["groups"] = groups
        args["groupIds"] = groupIds
        args["myGroups"] = myGroupsIds
        args["groupFollowers"] = groupFollowers
        args["pendingConnections"] = pendingConnections
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            yield renderScriptBlock(request, "groups.mako", "viewOptions",
                                landing, "#groups-view", "set", args=[viewType])
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
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users, relation, userIds, blockedUsers, nextPageStart,\
            prevPageStart = yield people.getPeople(myKey, groupId,
                                               args['orgKey'], start = start)
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

            #if fromFetchMore:
            #    yield renderScriptBlock(request, "groups.mako",
            #                            "displayGroupMembers", landing,
            #                            "#next-load-wrapper", "replace", True,
            #                            handlers={}, **args)
            #else:
            #    yield renderScriptBlock(request, "groups.mako",
            #                            "displayGroupMembers", landing,
            #                            "#groups-wrapper", "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listPendingSubscriptions(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        args["menuId"] = "groups"

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            cols = yield db.get_slice(groupId, "pendingConnections")
            cols = utils.columnsToDict(cols)
            userIds = cols.keys()
            cols = yield db.multiget_slice(userIds, "entities", ["basic"])
            users = utils.multiSuperColumnsToDict(cols)
            args["entities"] = users
        else:
            args["entities"] = []

        args["heading"] = "Pending Requests"
        args["groupId"] = groupId

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "pendingRequests",
                                    landing, "#groups-wrapper", "set", **args)


    @defer.inlineCallbacks
    def _invite(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        landing = not self._ajax

        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userId = utils.getRequestArg(request, "invitee")
        #cols = yield db.get_slice(emailId, "userAuth", ["user"])
        #if not cols:
        #    raise errors.InvalidRequest()
        #userId = cols[0].column.value
        args["groupId"] = groupId
        args["heading"] = group["basic"]["name"]

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if myKey in group['admins']:
            #TODO: dont add banned users
            yield self._addMember(request, groupId, userId, myOrgId)
            #yield self._listGroupMembers(request)
            refreshFeedScript = """
                $("#group_add_invitee").attr("value", "")
                """
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
            yield render(request,"groups.mako", **args)
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
            availableActions = ["approve", "reject", "block", "unblock",
                                "invite", "follow", "unfollow", "subscribe",
                                "unsubscribe", "create"]
            if action in availableActions:
                d = getattr(self, "_" + request.postpath[0])(request)

        return self._epilogue(request, d)
