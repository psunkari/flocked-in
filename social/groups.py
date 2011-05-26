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


from social             import base, Db, utils, errors, feed, people
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
        groupId = yield utils.getValidEntityId(request, "id", "group")

        try:
            cols = yield Db.get(myKey, "entityGroupsMap", groupId)
            yield Db.insert(groupId, "followers", "", myKey)
            args["groupId"]=groupId
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[myKey]}
            yield renderScriptBlock(request, "groups.mako", "userActions",
                                    landing, "#user-actions-%s" %(groupId),
                                    "replace", **args)
        except ttypes.NotFoundException:
            pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        groupId = yield utils.getValidEntityId(request, "id", "group")
        try:
            cols = yield Db.get(myKey, "entityGroupsMap", groupId)
            yield Db.remove(groupId, "followers", myKey)

            args["groupId"]=groupId
            args["myGroups"] = [groupId]
            args["pendingConnections"] = {}
            args["groupFollowers"] = {groupId:[]}
            yield renderScriptBlock(request, "groups.mako", "userActions",
                                    landing, "#user-actions-%s" %(groupId),
                                    "replace", **args)
        except ttypes.NotFoundException:
            pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addMember(self, request, groupId, userId, orgId):
        deferreds = []
        itemType = "activity"
        relation = Relation(userId, [])
        cols = yield Db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)

        responseType = "I"
        acl = {"accept":{"groups":[groupId], "followers":[], "friends":[]}}
        _acl = pickle.dumps(acl)

        itemId = utils.getUniqueKey()
        item = utils.createNewItem(request, "activity", userId,
                                   acl, "groupJoin", orgId)
        item["meta"]["target"] = groupId

        d1 = Db.insert(userId, "entityGroupsMap", "", groupId)
        d2 = Db.insert(groupId, "followers", "", userId)
        d3 = Db.insert(groupId, "groupMembers", itemId, userId)
        d4 = Db.batch_insert(itemId, 'items', item)

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
        groupId = yield utils.getValidEntityId(request, "id", "group")
        cols = yield Db.get(groupId, "entities", "access", "basic")
        access = cols.column.value
        myGroups = []
        pendingRequests = {}
        groupFollowers = {groupId:[]}


        cols = yield Db.get_slice(groupId, "bannedUsers", [myKey])
        if cols:
            log.msg("userid %s banned by admin" %(myKey))
            raise errors.UserBanned()

        try:
            cols = yield Db.get(myKey, "entityGroupsMap", groupId)
        except ttypes.NotFoundException:
            #add to pending connections
            if access == "public":
                yield self._addMember(request, groupId, myKey, myOrgId)
                myGroups.append(groupId)
                groupFollowers[groupId].append(myKey)
            else:
                yield Db.insert(myKey, "pendingConnections", '0', groupId)
                yield Db.insert(groupId, "pendingConnections", '1', myKey)
                #notify admin of the group
                cols = yield Db.get_slice(groupId, "entities", ["admins"])
                admins = utils.supercolumnsToDict(cols)

                for admin in admins["admins"]:
                    commentOwner = myKey
                    responseType = "G"
                    value = ":".join([responseType, commentOwner, groupId, '', admin])
                    timeUUID = uuid.uuid1().bytes
                    yield Db.insert(admin, "notifications", groupId, timeUUID)
                    yield Db.batch_insert(admin, "notificationItems", {groupId:{timeUUID:value}})

                pendingRequests[groupId]=myKey
            args["pendingConnections"] = pendingRequests
            args["groupFollowers"] = groupFollowers
            args["groupId"] = groupId
            args["myGroups"] = myGroups
            yield renderScriptBlock(request, "groups.mako", "userActions",
                                    landing, "#user-actions-%s" %(groupId),
                                    "replace", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _acceptSubscription(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield Db.get(groupId, "pendingConnections", userId)
                yield Db.remove(groupId, "pendingConnections", userId)
                yield Db.remove(userId, "pendingConnections", groupId)
                yield self._addMember(request, groupId, userId, myOrgId)
            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _rejectSubscription(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield Db.get(groupId, "pendingConnections", userId)
                yield Db.remove(groupId, "pendingConnections", userId)
                yield Db.remove(userId, "pendingConnections", groupId)
                # notify user that the moderator rejected.
            except ttypes.NotFoundException:
                pass


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _blockUser(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)

        if myKey == userId and myKey in group["admins"] \
            and len(group["admins"]) == 1:
            log.msg("Admin can't be banned from group")
            raise errors.InvalidRequest()

        if myKey in group["admins"]:
            # if the request is pending, remove the request
            yield Db.remove(groupId, "pendingConnections", userId)
            yield Db.remove(userId, "pendingConnections", groupId)

            # if the users is already a member, remove the user from the group
            yield Db.remove(groupId, "groupMembers", userId)
            yield Db.remove(groupId, "followers", userId)
            yield Db.remove(userId, "entityGroupsMap", groupId)

            yield Db.insert(groupId, "bannedUsers", '', userId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unBlockUser(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)

        if myKey in group["admins"]:
            # if the request is pending, remove the request
            yield Db.remove(groupId, "bannedUsers", userId)
            log.msg("unblocked user %s from group %s"%(userId, groupId))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unsubscribe(self, request):
        appchange, script, args, myId = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgId = args["orgKey"]

        groupId = yield utils.getValidEntityId(request, "id", "group")
        userGroup = yield Db.get_slice(myId, "entityGroupsMap", [groupId])
        if not userGroup:
            raise errors.InvalidRequest()

        itemType = "activity"
        responseType = "I"
        args["groupId"] = groupId
        args["myGroups"] = []
        args["groupFollowers"] = {groupId:[]}
        args["pendingConnections"] = []

        itemId = utils.getUniqueKey()
        acl = {"accept":{"groups":[groupId], "followers":[], "friends":[]}}
        _acl = pickle.dumps(acl)
        item = utils.createNewItem(request, itemType, myId,
                                   acl, "groupLeave", orgId)
        item["meta"]["target"] = groupId

        d1 = Db.remove(groupId, "followers", myId)
        d2 = Db.remove(myId, "entityGroupsMap", groupId)
        d3 = Db.batch_insert(itemId, 'items', item)
        d4 = Db.remove(groupId, "groupMembers", myId)
        #d4 = Db.insert(groupId, "groupMembers", itemId, myId)

        d5 = feed.pushToFeed(myId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, myId)

        d6 = feed.pushToOthersFeed(myId, item["meta"]["uuid"], itemId, itemId,
                                   _acl, responseType, itemType, myId)
        d7 =  renderScriptBlock(request, "groups.mako", "userActions",
                                landing, "#user-actions-%s" %(groupId),
                                "replace", **args)
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
        allowExternal = utils.getRequestArg(request, "external") or "closed"

        if allowExternal not in ("open", "closed"):
            raise errors.InvalidRequest()

        if not name:
            raise errors.MissingParams()

        groupId = utils.getUniqueKey()
        meta = {"name":name, "type":"group",
                "access":access, "orgKey":args["orgKey"],
                "allowExternalUsers": allowExternal}
        admins = {myKey:''}
        if description:
            meta["desc"] = description

        dp = utils.getRequestArg(request, "dp")
        if dp:
            avatar = yield saveAvatarItem(groupId, dp)
            meta["avatar"] = avatar

        yield Db.batch_insert(groupId, "entities", {"basic": meta,
                                                    "admins": admins})
        yield Db.insert(orgKey, "entityGroupsMap", '', groupId)
        request.redirect("/feed?id=%s"%(groupId))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderCreate(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgKey = args["orgKey"]

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        if script:
             yield renderScriptBlock(request, "groups.mako", "createGroup",
                                    landing, "#center-content", "set", **args)


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

        viewTypes = ['myGroups', 'allGroups']
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
        entityId = None
        entityId = myId if viewType == 'myGroups' else orgId

        #TODO: list the groups in sorted order.
        cols = yield Db.get_slice(entityId, 'entityGroupsMap',
                                  start=start, count=toFetchCount)
        groupIds = utils.columnsToDict(cols, ordered=True).keys()
        toFetchGroups.update(set(groupIds))

        cols = yield Db.get_slice(myId, "entityGroupsMap",
                                  start=start, count=toFetchCount)
        myGroupsIds = utils.columnsToDict(cols, ordered=True).keys()

        if len(groupIds) > count:
            nextPageStart = utils.encodeKey(groupIds[-1])
            groupIds = groupIds[0:count]

        if start:
            cols = yield Db.get_slice(entityId, 'entityGroupsMap', start=start,
                                      count=toFetchCount,  reverse=True)
            if len(cols) > 1:
                prevPageStart = utils.encodeKey(cols[-1].column.name)

        if toFetchGroups:
            groups = yield Db.multiget_slice(toFetchGroups, "entities", ["basic"])
            groups = utils.multiSuperColumnsToDict(groups)
            groupFollowers = yield Db.multiget_slice(toFetchGroups, "followers", names=[myId])
            groupFollowers = utils.multiColumnsToDict(groupFollowers)
            cols = yield Db.get_slice(myId, 'pendingConnections', toFetchGroups)
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
        groupId = yield utils.getValidEntityId(request, "id", "group")
        start = utils.getRequestArg(request, 'start') or ''
        fromFetchMore = ((not landing) and (not appchange) and start)

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
            if fromFetchMore:
                yield renderScriptBlock(request, "groups.mako",
                                        "displayGroupMembers", landing,
                                        "#next-load-wrapper", "replace", True,
                                        handlers={}, **args)
            else:
                yield renderScriptBlock(request, "groups.mako",
                                        "displayGroupMembers", landing,
                                        "#groups-wrapper", "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listPendingSubscriptions (self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId = yield utils.getValidEntityId(request, "id", "group")

        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if myKey in group["admins"]:
            #or myKey in moderators #if i am moderator
            cols = yield Db.get_slice(groupId, "pendingConnections")
            cols = utils.columnsToDict(cols)
            userIds = cols.keys()
            cols = yield Db.multiget_slice(userIds, "entities", ["basic"])
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
    def _inviteMember(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        landing = not self._ajax

        groupId = yield utils.getValidEntityId(request, "id", "group")
        emailId = utils.getRequestArg(request, "uid")
        cols = yield Db.get_slice(emailId, "userAuth", ["user"])
        if not cols:
            raise error.InvalidRequest()
        userId = cols[0].column.value
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)
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
            yield self._listGroupMembers(request)


    @defer.inlineCallbacks
    def _renderInviteMembers(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        myOrgId = args["orgKey"]
        landing = not self._ajax

        groupId = yield utils.getValidEntityId(request, "id", "group")
        group = yield Db.get_slice(groupId, "entities", ["basic", "admins"])
        group = utils.supercolumnsToDict(group)
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
        elif segmentCount == 1 and request.postpath[0]=="members":
            d = self._listGroupMembers(request)
        elif segmentCount == 1 and request.postpath[0] == "create":
            d = self._renderCreate(request)
        elif segmentCount == 1 and request.postpath[0] == "pending":
            d = self._listPendingSubscriptions(request)
        elif segmentCount == 1 and request.postpath[0] == "unblock":
            d = self._unBlockUser(request)
        elif segmentCount == 1 and request.postpath[0] == "invite":
            d = self._renderInviteMembers(request)
        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 1 and request.postpath[0] == "approve":
            d = self._acceptSubscription(request)
        elif segmentCount == 1 and request.postpath[0] == "reject":
            d = self._rejectSubscription(request)
        elif segmentCount == 1 and request.postpath[0] == "block":
            d = self._blockUser(request)
        elif segmentCount == 1 and request.postpath[0] == "unblock":
            d = self._unBlockUser(request)
        elif segmentCount == 1 and request.postpath[0] == "invite":
            d = self._inviteMember(request)
        elif segmentCount == 1:
            d = getattr(self, "_" + request.postpath[0])(request)

        return self._epilogue(request, d)
