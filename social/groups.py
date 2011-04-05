from twisted.web        import server
from twisted.python     import log
from twisted.internet   import defer
from telephus.cassandra import ttypes


from social             import base, Db, utils, errors, feed, profile
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock


class GroupsResource(base.BaseResource):
    isLeaf= True

    @defer.inlineCallbacks
    def _follow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")

        try:
            cols = yield Db.get(myKey, "userGroups", groupId)
            yield Db.insert(groupId, "followers", "", myKey)
        except ttypes.NotFoundException:
            pass

    @defer.inlineCallbacks
    def _unfollow(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        try:
            cols = yield Db.get(myKey, "userGroups", groupId)
            yield Db.remove(groupId, "followers", myKey)
        except ttypes.NotFoundException:
            pass

    @defer.inlineCallbacks
    def _addMember(self, request, groupId, userId, acl="public"):

        itemId = utils.getUniqueKey()
        item = utils.createNewItem(request, "activity", userId, acl)
        item["meta"]["subType"] = "group"
        item["meta"]["target"] = groupId
        yield Db.insert(userId, "userGroups", "", groupId)
        yield Db.insert(groupId, "followers", "", userId)
        yield Db.insert(groupId, "groupMembers", itemId, userId)
        yield Db.batch_insert(itemId, 'items', item)

        groupFollowers = yield Db.get_slice(groupId, "followers")
        groupFollowers = utils.columnsToDict(groupFollowers)

        #update followers feed
        #notify user


    @defer.inlineCallbacks
    def _subscribe(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        cols = yield Db.get(groupId, "entities", "access", "basic")
        access = cols.column.value

        cols = yield Db.get_slice(groupId, "bannedUsers", [myKey])
        if cols:
            log.msg("userid %s banned by admin" %(myKey))
            raise errors.UserBanned()

        try:
            cols = yield Db.get(myKey, "userGroups", groupId)
        except ttypes.NotFoundException:
            #add to pending connections
            if access == "public":
                yield self._addMember(request, groupId, myKey)
            else:
                yield Db.insert(myKey, "pendingConnections", '0', groupId)
                yield Db.insert(groupId, "pendingConnections", '1', myKey)

    @defer.inlineCallbacks
    def _acceptSubscription(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic"])
        group = utils.supercolumnsToDict(group)

        if myKey == group["basic"]["admin"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield Db.get(groupId, "pendingConnections", userId)
                yield Db.remove(groupId, "pendingConnections", userId)
                yield Db.remove(userId, "pendingConnections", groupId)
                yield self._addMember(request, groupId, userId)
            except ttypes.NotFoundException:
                pass

    @defer.inlineCallbacks
    def _rejectSubscription(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic"])
        group = utils.supercolumnsToDict(group)

        if myKey == group["basic"]["admin"]:
            #or myKey in moderators #if i am moderator
            try:
                cols = yield Db.get(groupId, "pendingConnections", userId)
                yield Db.remove(groupId, "pendingConnections", userId)
                yield Db.remove(userId, "pendingConnections", groupId)
                # notify user that the moderator rejected.
            except ttypes.NotFoundException:
                pass


    @defer.inlineCallbacks
    def _blockUser(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic"])
        group = utils.supercolumnsToDict(group)

        if myKey == userId and myKey == group["basic"]["admin"]:
            log.msg("Admin can't be banned from group")
            raise errors.InvalidRequest()

        if myKey == group["basic"]["admin"]:
            # if the request is pending, remove the request
            yield Db.remove(groupId, "pendingConnections", userId)
            yield Db.remove(userId, "pendingConnections", groupId)

            # if the users is already a member, remove the user from the group
            yield Db.remove(groupId, "groupMembers", userId)
            yield Db.remove(groupId, "followers", userId)
            yield Db.remove(userId, "userGroups", groupId)

            yield Db.insert(groupId, "bannedUsers", '', userId)

    @defer.inlineCallbacks
    def _unBlockUser(self, request):

        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")
        userId = yield utils.getValidEntityId(request, "uid", "user")
        group = yield Db.get_slice(groupId, "entities", ["basic"])
        group = utils.supercolumnsToDict(group)

        if myKey == group["basic"]["admin"]:
            # if the request is pending, remove the request
            yield Db.remove(groupId, "bannedUsers", userId)
            log.msg("unblocked user %s from group %s"%(userId, groupId))

    @defer.inlineCallbacks
    def _unsubscribe(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId = yield utils.getValidEntityId(request, "id", "group")

        groupMember = yield Db.get_slice(groupId, "groupMembers", [myKey])
        userGroup = yield Db.get_slice(myKey, "userGroups", [groupId])

        if not groupMember or not userGroup:
            raise errors.InvalidRequest()
        groupMember = utils.columnsToDict(groupMember)
        itemId = groupMember[myKey]

        #yield Db.remove(itemId, "items")
        yield Db.remove(groupId, "groupMembers", myKey)
        yield Db.remove(groupId, "followers", myKey)
        yield Db.remove(myKey, "userGroups", groupId)


    @defer.inlineCallbacks
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
        meta = {"name":name, "admin":myKey, "type":"group",
                "access":access, "orgKey":args["orgKey"],
                "allowExternalUsers": allowExternal}
        if description:
            meta["desc"] = description

        dp = utils.getRequestArg(request, "dp")
        if dp:
            avatar = yield profile.saveAvatarItem(groupId, dp)
            meta["avatar"] = avatar

        yield Db.batch_insert(groupId, "entities", {"basic": meta})
        yield Db.insert(orgKey, "orgGroups", '', groupId)
        request.redirect("/feed?id=%s"%(groupId))

    @defer.inlineCallbacks
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
                                    landing, "#groups-wrapper", "set", **args)


    @defer.inlineCallbacks
    def _listGroups(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        orgKey = args["orgKey"]

        toFetchGroups = set()

        cols = yield Db.get_slice(orgKey, 'orgGroups')
        orgGroupIds = utils.columnsToDict(cols).keys()
        toFetchGroups.update(set(orgGroupIds))

        myGroups = yield Db.get_slice(myKey, "userGroups")
        myGroups = utils.columnsToDict(myGroups).keys()
        toFetchGroups.update(set(myGroups))

        groups = yield Db.multiget_slice(toFetchGroups, "entities", ["basic"])
        groupFollowers = yield Db.multiget_slice(toFetchGroups, "followers")

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        args["groups"] = utils.multiSuperColumnsToDict(groups)
        args["myGroups"] = myGroups
        args["groupFollowers"] = utils.multiColumnsToDict(groupFollowers)

        if script:
             yield renderScriptBlock(request, "groups.mako", "displayGroups",
                                    landing, "#groups-wrapper", "set", **args)


    @defer.inlineCallbacks
    def _listGroupMembers(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax
        groupId = yield utils.getValidEntityId(request, "id", "group")

        groupMembers = yield Db.get_slice(groupId, "groupMembers")
        groupMembers = utils.columnsToDict(groupMembers).keys()

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users = yield Db.multiget_slice(groupMembers, "entities", ["basic"])
        users = utils.multiSuperColumnsToDict(users)
        relation = Relation(myKey, users.keys())
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initPendingList(),
                                  relation.initSubscriptionsList()])
        args["relations"] = relation
        args["users"] = users
        args["heading"] = "Members"

        if script:

            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "displayGroupMembers",
                                    landing, "#groups-wrapper", "set", **args)


    @defer.inlineCallbacks
    def _listPendingSubscriptions (self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        landing = not self._ajax

        groupId = yield utils.getValidEntityId(request, "id", "group")

        group = yield Db.get_slice(groupId, "entities", ["basic"])
        group = utils.supercolumnsToDict(group)

        if script and landing:
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)



        if myKey == group["basic"]["admin"]:
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



    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listGroups(request)
        elif segmentCount == 1 and request.postpath[0]=="members":
            d = self._listGroupMembers(request)
        elif segmentCount == 1 and request.postpath[0] == "create":
            d = self._renderCreate(request)
        elif segmentCount == 1 and request.postpath[0] == "admin":
            d = self._listPendingSubscriptions(request)
        elif segmentCount == 1 and request.postpath[0] == "unblock":
            d = self._unBlockUser(request)

        return self._epilogue(request, d)


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
        elif segmentCount == 1:
            d = getattr(self, "_" + request.postpath[0])(request)

        return self._epilogue(request, d)
