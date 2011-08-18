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
from social.constants   import PEOPLE_PER_PAGE
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args
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
        yield db.remove(groupId, "pendingConnections", userId)
        yield db.remove(userId, "pendingConnections", groupId)

        cols = yield db.get_slice(groupId, "latest", ['groups'])
        cols = utils.supercolumnsToDict(cols)
        for tuuid, key in cols['groups'].items():
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

        d5 = feed.pushToFeed(groupId, item["meta"]["uuid"], itemId,
                             itemId, responseType, itemType, userId)
        d6 = feed.pushToOthersFeed(userId, item["meta"]["uuid"], itemId, itemId,
                    _acl, responseType, itemType, userId, promoteActor=False)

        d7 = utils.updateDisplayNameIndex(userId, [groupId],
                                          userInfo['basic']['name'], None)

        deferreds = [d1, d2, d3, d4, d5, d6, d7]
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

        cols = yield db.get_slice(groupId, "blockedUsers", [myKey])
        if cols:
            raise errors.PermissionDenied(_("You are banned from joining the group by the administrator"))

        try:
            cols = yield db.get(myKey, "entityGroupsMap", groupId)
        except ttypes.NotFoundException:
            if access == "open":
                yield self._addMember(request, groupId, myKey, myOrgId)
                myGroups.append(groupId)
                groupFollowers[groupId].append(myKey)
            else:
                # Add to pending connections
                yield db.insert(myKey, "pendingConnections", '0', groupId)
                yield db.insert(groupId, "pendingConnections", '1', myKey)

                yield self._notify(groupId, myKey)
                pendingRequests[groupId] = myKey

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
            try:
                cols = yield db.get(groupId, "pendingConnections", userId)
                yield self._removeFromPending(groupId, userId)
                yield self._addMember(request, groupId, userId, myOrgId)
                yield renderScriptBlock(request, "groups.mako",
                                        "_pendingGroupRequestsActions", False,
                                        '#pending-group-request-actions-%s' %(userId),
                                        "set", args=[groupId, userId, "accept"])

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
            try:
                cols = yield db.get(groupId, "pendingConnections", userId)
                yield self._removeFromPending(groupId, userId)
                yield renderScriptBlock(request, "groups.mako",
                                        "_pendingGroupRequestsActions", False,
                                        '#pending-group-request-actions-%s' %(userId),
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
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey == userId and myKey in group["admins"]:
            raise errors.InvalidRequest(_("An administrator cannot ban himself/herself from the group"))

        if myKey in group["admins"]:
            try:
                cols = yield db.get(groupId, "pendingConnections", userId)
                yield self._removeFromPending(groupId, userId)
                yield renderScriptBlock(request, "groups.mako",
                                        "_pendingGroupRequestsActions", False,
                                        '#pending-group-request-actions-%s' %(userId),
                                        "set", args=[groupId, userId, "block"])
            except ttypes.NotFoundException:
                # If the users is already a member, remove the user from the group
                yield db.remove(groupId, "groupMembers", userId)
                yield db.remove(groupId, "followers", userId)
                yield db.remove(userId, "entityGroupsMap", groupId)

            # Add user to blocked users
            yield db.insert(groupId, "blockedUsers", '', userId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unblock(self, request):
        appchange, script, args, myKey = yield self._getBasicArgs(request)
        groupId, group = yield utils.getValidEntityId(request, "id", "group",
                                                      columns=["admins"])
        userId, user = yield utils.getValidEntityId(request, "uid", "user")

        if myKey in group["admins"]:
            yield db.remove(groupId, "blockedUsers", userId)


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
            script = "$$.ui.bindFormSubmit('#group_form', function(){$('#add-user-wrapper').empty();$$.fetchUri('/groups');})"
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
            startKey, startGroupId = start.split(":")

        toFetchStart = startKey
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
            userIds.extend([(col.column.name, toFetchGroup) for col in cols])
            if len(userIds) >= toFetchCount:
                break
            if len(cols) < toFetchCount:
                if index + 1 < len(managedGroupIds):
                    index = index+1
                    toFetchGroup = managedGroupIds[index]
                    toFetchStart = ''
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
                tmpIds.extend([(col.column.name, toFetchGroup) for col in cols])

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

        viewTypes = ['myGroups', 'allGroups', 'adminGroups', 'pendingRequests']
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
            yield render(request,"groups.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "groups.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if viewType != 'pendingRequests':
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
                groupIds = utils.columnsToDict(cols, ordered=True).keys()
                toFetchGroups.update(set(groupIds))
            elif viewType == 'adminGroups':
                try:
                    cols = yield db.get_slice(myId, "entities",
                                              super_column='adminOfGroups',
                                              start=start, count=toFetchCount)
                    groupIds = utils.columnsToDict(cols, ordered=True).keys()
                    toFetchGroups.update(set(groupIds))
                except ttypes.NotFoundException:
                    pass

            if toFetchGroups:
                cols = yield db.get_slice(myId, "entityGroupsMap", list(toFetchGroups))
            else:
                cols = []
            myGroupsIds = utils.columnsToDict(cols, ordered=True).keys()

            if len(groupIds) > count:
                nextPageStart = utils.encodeKey(groupIds[-1])
                groupIds = groupIds[0:count]

            if start:
                if viewType in ['myGroups', 'allGroups']:
                  try:
                    cols = yield db.get_slice(entityId, 'entityGroupsMap',
                                              start=start, count=toFetchCount,
                                              reverse=True)
                  except Exception, e:
                    log.err(e)
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
                cols = yield db.get_slice(myId, 'pendingConnections', toFetchGroups)
                pendingConnections = dict((x.column.name, x.column.value) for x in cols)
            args["groups"] = groups
            args["groupIds"] = groupIds
            args["myGroups"] = myGroupsIds
            args["groupFollowers"] = groupFollowers
            args["pendingConnections"] = pendingConnections
            args['nextPageStart'] = nextPageStart
            args['prevPageStart'] = prevPageStart
        else:
            userIds, entities, prevPageStart, nextPageStart = yield self._getPendingGroupRequests(request)
            args["userIds"] = userIds
            args["entities"] = entities
            args["prevPageStart"] = prevPageStart
            args["nextPageStart"] = nextPageStart

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
            yield render(request,"groups.mako", **args)
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
        start = utils.getRequestArg(request, 'start') or ''
        count = PEOPLE_PER_PAGE
        toFetchCount = count+1
        nextPageStart = None
        prevPageStart = None

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
            cols = yield db.get_slice(groupId, "pendingConnections",
                                      start=start, count=toFetchCount)
            cols = utils.columnsToDict(cols, ordered=True)
            userIds = cols.keys()
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

        if script:
            yield renderScriptBlock(request, "groups.mako", "titlebar",
                                    landing, "#titlebar", "set", **args)
            yield renderScriptBlock(request, "groups.mako", "pendingRequests",
                                    landing, "#groups-wrapper", "set", **args)
            yield renderScriptBlock(request, 'groups.mako', "pendingRequestsPaging",
                                    landing, "#groups-paging", "set", **args)



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
            # TODO: dont add blocked users
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
            d.addCallback(_updatePendingGroupRequestCount)

        return self._epilogue(request, d)
