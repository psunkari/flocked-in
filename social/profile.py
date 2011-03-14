
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
            rtype, itemId, convId, convType, convOwnerId = value

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
                reasonStr[value] = _("liked a comment on %s's %s")
                userItems.append(value)
            elif rtype == "C" and convOwnerId != userKey:
                reasonStr[value] = _("commented on %s's %s")
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
                d =  plugins[itemType].getRootData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchUsers_, toFetchGroups_ = ret
                toFetchUsers.update(toFetchUsers_)
                toFetchGroups.update(toFetchGroups_)

        d2 = Db.multiget(toFetchUsers, "users", "basic")
        d3 = Db.multiget(toFetchGroups, "groups", "basic")

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
    def _follow(self, request):
        targetKey = yield utils.getValidUserKey(request, "id")
        myKey = auth.getMyKey(request)

        d1 = Db.insert(myKey, "subscriptions", "", targetKey)
        d2 = Db.insert(targetKey, "followers", "", myKey)
        yield d1
        yield d2

        request.finish()

    def _unfollow(self, request):
        targetKey = yield utils.getValidUserKey(request, "id")
        myKey = auth.getMyKey(request)

        try:
            d1 = Db.remove(myKey, "subscriptions", targetKey)
            d2 = Db.remove(targetKey, "followers", myKey)
            yield d1
            yield d2
        except ttypes.NotFoundException:
            pass

        request.finish()

    @defer.inlineCallbacks
    def _friend(self, request):
        targetKey = yield utils.getValidUserKey(request, "id")
        myKey = auth.getMyKey(request)

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
        calls = None
        try:
            cols = yield Db.get(myKey, "pendingConnections", targetKey)
            d1 = Db.remove(myKey, "pendingConnections", targetKey)
            d2 = Db.remove(targetKey, "pendingConnections", myKey)
            d3 = Db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d4 = Db.batch_insert(targetKey, "connections", {myKey: {'__default__':''}})
            calls = defer.DeferredList([d1, d2, d3])
        except ttypes.NotFoundException:
            d1 = Db.insert(myKey, "pendingConnections", '0', targetKey)
            d2 = Db.insert(targetKey, "pendingConnections", '1', myKey)
            calls = defer.DeferredList([d1, d2])

        yield calls
        request.finish()

    @defer.inlineCallbacks
    def _unfriend(self, request):
        targetKey = yield utils.getValidUserKey(request, "id")
        myKey = auth.getMyKey(request)

        try:
            d1 = Db.remove(myKey, "connections", None, targetKey)
            d2 = Db.remove(targetKey, "connections", None, myKey)
            yield d1
            yield d2
        except ttypes.NotFoundException:
            pass

        request.finish()

    def render_POST(self, request):
        if len(request.postpath) == 1:
            action = request.postpath[0]
            d = None
            if action == "friend":
                d = self._friend(request)
            elif action == "unfriend":
                d = self._unfriend(request)
            elif action == "follow":
                d = self._follow(request)
            elif action == "unfollow":
                d = self._unfollow(request)
            else:
                self._default(request)

        return server.NOT_DONE_YET

    def render_GET(self, request):
        request.addCookie("_page", "profile", path="/")
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self._render(request)
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            d.addErrback(errback)
            return server.NOT_DONE_YET
        if segmentCount == 1 and request.postpath[0]== 'edit':
            d = self._renderEditProfile(request)
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            d.addErrback(errback)
            return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _renderEditProfile(self, request):
        (appchange, script, args) = self._getBasicArgs(request)

        myKey = args["myKey"]
        cols = yield Db.multiget_slice([myKey], "users")
        args["me"] = utils.supercolumnsToDict(cols[myKey])
        args["users"] = utils.multiSuperColumnsToDict(cols)
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

        if detail == "avatar":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editAvatar",
                                    landing, "#profile-content", "set", **args)
        if detail == "detail":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editDetail",
                                    landing, "#profile-content", "set", **args)

        request.finish()


    @defer.inlineCallbacks
    def _render(self, request):
        (appchange, script, args) = self._getBasicArgs(request)

        myKey = args["myKey"]
        userKey = utils.getRequestArg(request, "id") or myKey
        request.addCookie('cu', userKey, path="/ajax/profile")

        cols = yield Db.multiget_slice([myKey, userKey], "users")
        args["me"] = utils.supercolumnsToDict(cols[myKey])
        if cols[userKey] and len(cols[userKey]):
            args["user"] = utils.supercolumnsToDict(cols[userKey])
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
        relation = Relation(myKey, userKey)
        args["relation"] = relation
        yield defer.DeferredList([relation.checkIsFriend(),
                                  relation.checkIsFollowing()])

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
                                           "users", super_column="basic")
            rawUserData = {}
            for key, data in cols.items():
                if len(data) > 0:
                    rawUserData[key] = utils.columnsToDict(data)
            args["rawUserData"] = rawUserData

            # List the users groups (and look for groups common with me)
            cols = yield Db.multiget_slice([myKey, userKey], "groups")
            myGroups = set(utils.columnsToDict(cols[userKey]).keys())
            userGroups = set(utils.columnsToDict(cols[userKey]).keys())
            commonGroups = myGroups.intersection(userGroups)
            if len(userGroups) > 10:
                userGroups = sample(userGroups, 10)
            args["groups"] = userGroups
            args["commonGroups"] = commonGroups

            groupsToFetch = commonGroups.union(userGroups)
            cols = yield Db.multiget_slice(groupsToFetch, "groups",
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

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "profile.mako", **args)

        request.finish()
