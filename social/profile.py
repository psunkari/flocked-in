
from random                 import sample

from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social                 import Db, auth, utils, base, plugins, _, __


class ProfileResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @defer.inlineCallbacks
    def _getUserItems(self, userKey, count=10):
        toFetchItems = set()
        toFetchUsers = set()
        toFetchResponses = set()
        toFetchGroups = set()
        responses = {}
        args = {"myKey":userKey}
        convs = []
        userItemsRaw = []
        userItems = []
        reasonStr = {}

        toFetchUsers.add(userKey)
        cols = yield Db.get_slice(userKey, "userItems", reverse=True, count=count)
        for col in cols:
            value = tuple(col.column.value.split(":"))
            rtype, itemId, convId, convType, convOwnerId, commentSnippet = value
            commentSnippet = """<span class="snippet"> "%s" </span>""" %(_(commentSnippet))
            toFetchUsers.add(convOwnerId)
            if rtype == 'I':
                toFetchItems.add(convId)
                toFetchResponses.add(convId)
                convs.append(convId)
                userItems.append(value)
            elif rtype == "L" and itemId == convId and convOwnerId != userKey:
                reasonStr[value] = _("liked %s's %s")
                userItems.append(value)
            elif rtype == "L"  and convOwnerId != userKey:
                reasonStr[value] = _("liked") + "%s" %(commentSnippet) + _(" comment on %s's %s")
                userItems.append(value)
            elif rtype == "C" and convOwnerId != userKey:
                reasonStr[value] = "%s"%(commentSnippet) + _(" on %s's %s")
                userItems.append(value)

        itemResponses = yield Db.multiget_slice(toFetchResponses, "itemResponses",
                                                count=2, reverse=True)
        for convId, comments in itemResponses.items():
            responses[convId] = []
            for comment in comments:
                userKey_, itemKey = comment.column.value.split(':')
                if itemKey not in toFetchItems:
                    responses[convId].insert(0,itemKey)
                    toFetchItems.add(itemKey)
                    toFetchUsers.add(userKey_)

        items = yield Db.multiget(toFetchItems, "items", "meta")
        items = utils.multiSuperColumnsToDict(items)
        args["items"] = items
        extraDataDeferreds = []

        for convId in convs:
            itemType = items[convId]["meta"]["type"]
            if itemType in plugins:
                d =  plugins[itemType].fetchData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchUsers_, toFetchGroups_ = ret
                toFetchUsers.update(toFetchUsers_)
                toFetchGroups.update(toFetchGroups_)

        d2 = Db.multiget(toFetchUsers, "entities", "basic")
        d3 = Db.multiget(toFetchGroups, "entities", "basic")

        fetchedUsers = yield d2
        fetchedGroups = yield d3
        users = utils.multiSuperColumnsToDict(fetchedUsers)
        groups = utils.multiSuperColumnsToDict(fetchedGroups)

        del args['myKey']
        data = {"users":users, "groups":groups,
                "reasonStr":reasonStr, "userItems":userItems,
                "responses":responses}
        args.update(data)
        defer.returnValue(args)


    @defer.inlineCallbacks
    def _follow(self, myKey, targetKey):
        d1 = Db.insert(myKey, "subscriptions", "", targetKey)
        d2 = Db.insert(targetKey, "followers", "", myKey)
        yield d1
        yield d2


    @defer.inlineCallbacks
    def _unfollow(self, myKey, targetKey):
        try:
            d1 = Db.remove(myKey, "subscriptions", targetKey)
            d2 = Db.remove(targetKey, "followers", myKey)
            yield d1
            yield d2
        except ttypes.NotFoundException:
            pass


    @defer.inlineCallbacks
    def _friend(self, request, myKey, targetKey):
        if not utils.areFriendlyDomains(myKey, targetKey):
            raise errors.NotAllowed()

        # Circles are just tags that a user would set on his connections
        circles = request.args["circle"]\
                  if request.args.has_key("circle") else []
        circles.append("__default__")
        circlesMap = dict([(circle, '') for circle in circles])

        # Check if we have a request pending from this user.
        # If yes, this just becomes accepting a local pending request
        # Else create a friend request that will be pending on the target user
        calls = []
        try:
            cols = yield Db.get(myKey, "pendingConnections", targetKey)
            d1 = Db.remove(myKey, "pendingConnections", targetKey)
            d2 = Db.remove(targetKey, "pendingConnections", myKey)
            d3 = Db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d4 = Db.batch_insert(targetKey, "connections", {myKey: {'__default__':''}})
            calls = [d1, d2, d3]
        except ttypes.NotFoundException:
            d1 = Db.insert(myKey, "pendingConnections", '0', targetKey)
            d2 = Db.insert(targetKey, "pendingConnections", '1', myKey)
            calls = [d1, d2]

        yield defer.DeferredList(calls)


    @defer.inlineCallbacks
    def _unfriend(self, myKey, targetKey):
        deferreds = [Db.remove(myKey, "connections", None, targetKey),
                     Db.remove(targetKey, "connections", None, myKey),
                     Db.remove(myKey, "pendingConnections", targetKey),
                     Db.remove(targetKey, "pendingConnections", myKey)]
        yield defer.DeferredList(deferreds)


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        requestDeferred = utils.getValidEntityId(request, "id", "user")
        myKey = auth.getMyKey(request)

        def callback(targetKey):
            if segmentCount != 1:
                raise errors.InvalidRequest()

            actionDeferred = None
            action = request.postpath[0]
            if action == "friend":
                actionDeferred = self._friend(request, myKey, targetKey)
            elif action == "unfriend":
                actionDeferred = self._unfriend(myKey, targetKey)
            elif action == "follow":
                actionDeferred = self._follow(myKey, targetKey)
            elif action == "unfollow":
                actionDeferred = self._unfollow(myKey, targetKey)
            else:
                raise errors.InvalidRequest()

            relation = Relation(myKey, [targetKey])
            data = {"relations": relation}
            def fetchRelations(ign):
                return defer.DeferredList([relation.initFriendsList(),
                                           relation.initPendingList(),
                                           relation.initSubscriptionsList()])

            isProfile = (request.getCookie("_page") == "profile")
            def renderActions(ign):
                d = renderScriptBlock(request, "profile.mako", "user_actions",
                                False, "#user-actions-%s"%targetKey, "set",
                                args=[targetKey, False, not isProfile], **data)
                if isProfile:
                    def renderSubactions(ign):
                        return renderScriptBlock(request, "profile.mako",
                                    "user_subactions", False,
                                    "#user-subactions-%s"%targetKey, "set",
                                    args=[targetKey, False], **data)
                    d.addCallback(renderSubactions)
                return d

            actionDeferred.addCallback(fetchRelations)
            actionDeferred.addCallback(renderActions)
            return actionDeferred

        requestDeferred.addCallback(callback)
        return self._epilogue(request, requestDeferred)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0]== 'edit':
            d = self._renderEditProfile(request)

        return self._epilogue(request, d)


    @defer.inlineCallbacks
    def _renderEditProfile(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "profile.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "profile.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        detail = utils.getRequestArg(request, "dt") or "basic"
        args["detail"] = detail
        if detail == "basic":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editBasicInfo",
                                    landing, "#profile-content", "set", **args)
        if detail == "detail":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editDetail",
                                    landing, "#profile-content", "set", **args)


    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)

        userKey = utils.getRequestArg(request, "id") or myKey
        request.addCookie('cu', userKey, path="/ajax/profile")

        cols = yield Db.get_slice(userKey, "entities")
        if cols:
            user = utils.supercolumnsToDict(cols)
            if user["basic"]["type"] != "user":
                raise errors.UnknownUser()
            args["user"] = user

        else:
            raise errors.UnknownUser()

        detail = utils.getRequestArg(request, "dt") or "notes"
        args["detail"] = detail
        args["userKey"] = userKey

        if detail == "notes":
            userItems = yield self._getUserItems(userKey)
            args.update(userItems)

        # When scripts are enabled, updates are sent to the page as
        # and when we get the required data from the database.

        # When we are the landing page, we also render the page header
        # and all updates are wrapped in <script> blocks.
        landing = not self._ajax

        # User entered the URL directly
        # Render the header.  Other things will follow.
        if script and landing:
            yield render(request, "profile.mako", **args)

        # Start with displaying the template and navigation menu
        if script and appchange:
            yield renderScriptBlock(request, "profile.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        # Prefetch some data about how I am related to the user.
        # This is required in order to reliably filter our profile details
        # that I don't have access to.
        relation = Relation(myKey, [userKey])
        args["relations"] = relation
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initPendingList(),
                                  relation.initSubscriptionsList()])

        # Reload all user-depended blocks if the currently displayed user is
        # not the same as the user for which new data is being requested.
        newId = (request.getCookie('cu') != userKey) or appchange
        if script and newId:
            yield renderScriptBlock(request, "profile.mako", "summary",
                                    landing, "#profile-summary", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_subactions",
                                    landing, "#user-subactions", "set", **args)

        fetchedUsers = set()
        if script:
            yield renderScriptBlock(request, "profile.mako", "tabs", landing,
                                    "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "content", landing,
                                    "#profile-content", "set", **args)

        if newId or not script:
            # List the user's subscriptions
            cols = yield Db.get_slice(userKey, "subscriptions", count=11)
            subscriptions = set(utils.columnsToDict(cols).keys())
            args["subscriptions"] = subscriptions

            # List the user's followers
            cols = yield Db.get_slice(userKey, "followers", count=11)
            followers = set(utils.columnsToDict(cols).keys())
            args["followers"] = followers

            # List the users friends (if allowed and look for common friends)
            cols = yield Db.multiget_slice([myKey, userKey], "connections")
            myFriends = set(utils.supercolumnsToDict(cols[myKey]).keys())
            userFriends = set(utils.supercolumnsToDict(cols[userKey]).keys())
            commonFriends = myFriends.intersection(userFriends)
            args["commonFriends"] = commonFriends

            # Fetch item data (name and avatar) for subscriptions, followers,
            # user groups and common items.
            usersToFetch = followers.union(subscriptions, commonFriends)\
                                    .difference(fetchedUsers)
            cols = yield Db.multiget_slice(usersToFetch,
                                           "entities", super_column="basic")
            rawUserData = {}
            for key, data in cols.items():
                if len(data) > 0:
                    rawUserData[key] = utils.columnsToDict(data)
            args["rawUserData"] = rawUserData

            # List the users groups (and look for groups common with me)
            cols = yield Db.multiget_slice([myKey, userKey], "userGroups")
            myGroups = set(utils.columnsToDict(cols[userKey]).keys())
            userGroups = set(utils.columnsToDict(cols[userKey]).keys())
            commonGroups = myGroups.intersection(userGroups)
            if len(userGroups) > 10:
                userGroups = sample(userGroups, 10)
            args["groups"] = userGroups
            args["commonGroups"] = commonGroups

            groupsToFetch = commonGroups.union(userGroups)
            cols = yield Db.multiget_slice(groupsToFetch, "entities",
                                           super_column="basic")
            rawGroupData = {}
            for key, data in cols.items():
                if len(data) > 0:
                    rawGroupData[key] = utils.columnsToDict(data)
            args["rawGroupData"] = rawGroupData

        if script and newId:
            yield renderScriptBlock(request, "profile.mako", "user_subscriptions",
                                    landing, "#user-subscriptions", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_followers",
                                    landing, "#user-followers", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_me",
                                    landing, "#user-me", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "profile.mako", **args)

        request.finish()
