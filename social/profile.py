import PythonMagick
import imghdr
import uuid
from random                 import sample

from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social                 import db, utils, base, plugins, _, __
from social                 import constants, feed, errors, people
from social.logging         import dump_args, profile
from social.isocial         import IAuthInfo


class ProfileResource(base.BaseResource):
    isLeaf = True
    resources = {}


    # Add a notification (TODO: and send mail notifications to users
    # who prefer getting notifications on e-mail)
    @defer.inlineCallbacks
    def _notify(self, myId, targetId):
        timeUUID = uuid.uuid1().bytes
        yield db.insert(targetId, "latest", myId, timeUUID, "people")


    # Remove notifications about a particular user.
    # XXX: Assuming that there wouldn't be too many items here.
    @defer.inlineCallbacks
    def _removeFromPending(self, myId, targetId):
        yield db.remove(myId, "pendingConnections", targetId)
        yield db.remove(targetId, "pendingConnections", myId)

        cols = yield db.get_slice(myId, "latest", ['people'])
        cols = utils.supercolumnsToDict(cols)
        for tuuid, key in cols.get('people', {}).items():
            if key == targetId:
                yield db.remove(myId, "latest", tuuid, 'people')


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _getUserItems(self, request, userKey, start='', count=10):
        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username
        myOrgId = authinfo.organization

        toFetchItems = set()
        toFetchEntities = set()
        toFetchTags = set()
        toFetchResponses = set()
        toFetchCount = count + 1
        toFetchStart = utils.decodeKey(start) if start else ''
        fetchedUserItem = []
        responses = {}
        convs = []
        userItemsRaw = []
        userItems = []
        reasonStr = {}
        items = {}
        nextPageStart = None
        args = {"myKey": myKey}

        relation = Relation(myKey, [])
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initGroupsList()])

        toFetchEntities.add(userKey)

        while len(convs) < toFetchCount:
            cols = yield db.get_slice(userKey, "userItems", start=toFetchStart,
                                      reverse=True, count=toFetchCount)
            tmpIds = []
            for col in cols:
                convId = col.column.value.split(":")[2]
                if convId not in tmpIds and convId not in convs:
                    tmpIds.append(convId)
            (filteredConvs, deletedConvs) = yield feed.fetchAndFilterConvs\
                        (tmpIds, toFetchCount, relation, items, myKey, myOrgId)
            for col in cols[0:count]:
                convId = col.column.value.split(":")[2]
                if len(convs) == count or len(fetchedUserItem) == count*2:
                    nextPageStart = col.column.name
                    break
                if convId not in filteredConvs and convId not in convs:
                    continue
                fetchedUserItem.append(col)
                if convId not in convs:
                    convs.append(convId)
            if len(cols) < toFetchCount or nextPageStart:
                break
            if cols:
                toFetchStart = cols[-1].column.name
        if nextPageStart:
            nextPageStart = utils.encodeKey(nextPageStart)


        for col in fetchedUserItem:
            value = tuple(col.column.value.split(":"))
            rtype, itemId, convId, convType, convOwnerId, commentSnippet = value
            commentSnippet = """<span class="snippet"> "%s" </span>""" %(_(commentSnippet))
            toFetchEntities.add(convOwnerId)
            toFetchItems.add(convId)
            if rtype == 'I':
                toFetchResponses.add(convId)
                userItems.append(value)
            elif rtype == "L" and itemId == convId and convOwnerId != userKey:
                reasonStr[value] = _("liked %s's %s")
                userItems.append(value)
            elif rtype == "L"  and convOwnerId != userKey:
                r = "answer" if convType == 'question' else 'comment'
                reasonStr[value] = _("liked") + "%s" %(commentSnippet) + _("%s "%r) + _("on %s's %s")
                userItems.append(value)
            elif rtype in ["C", 'Q'] and convOwnerId != userKey:
                reasonStr[value] = "%s"%(commentSnippet) + _(" on %s's %s")
                userItems.append(value)

        itemResponses = yield db.multiget_slice(toFetchResponses, "itemResponses",
                                                count=2, reverse=True)
        for convId, comments in itemResponses.items():
            responses[convId] = []
            for comment in comments:
                userKey_, itemKey = comment.column.value.split(':')
                if itemKey not in toFetchItems:
                    responses[convId].insert(0,itemKey)
                    toFetchItems.add(itemKey)
                    toFetchEntities.add(userKey_)

        items = yield db.multiget_slice(toFetchItems, "items", ["meta", "tags"])
        items = utils.multiSuperColumnsToDict(items)
        args["items"] = items
        extraDataDeferreds = []

        for convId in convs:
            meta = items[convId]["meta"]
            itemType = meta["type"]
            toFetchEntities.add(meta["owner"])
            if "target" in meta:
                toFetchEntities.add(meta["target"])

            toFetchTags.update(items[convId].get("tags", {}).keys())

            if itemType in plugins:
                d =  plugins[itemType].fetchData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchEntities.update(ret)

        fetchedEntities = yield db.multiget(toFetchEntities, "entities", "basic")
        entities = utils.multiSuperColumnsToDict(fetchedEntities)

        tags = {}
        if toFetchTags:
            userOrgId = entities[userKey]["basic"]["org"]
            fetchedTags = yield db.get_slice(userOrgId, "orgTags", toFetchTags)
            tags = utils.supercolumnsToDict(fetchedTags)

        fetchedLikes = yield db.multiget(toFetchItems, "itemLikes", myKey)
        myLikes = utils.multiColumnsToDict(fetchedLikes)

        del args['myKey']
        data = {"entities": entities, "reasonStr": reasonStr,
                "tags": tags, "myLikes": myLikes, "userItems": userItems,
                "responses": responses, "nextPageStart":nextPageStart}
        args.update(data)
        defer.returnValue(args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _follow(self, myKey, targetKey):
        d1 = db.insert(myKey, "subscriptions", "", targetKey)
        d2 = db.insert(targetKey, "followers", "", myKey)
        yield d1
        yield d2


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, myKey, targetKey):
        d1 = db.remove(myKey, "subscriptions", targetKey)
        d2 = db.remove(targetKey, "followers", myKey)
        yield d1
        yield d2


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _friend(self, request, myKey, targetKey):
        # Circles are just tags that a user would set on his connections
        circles = utils.getRequestArg(request, 'circle', True) or []
        circles.append("__default__")
        circlesMap = dict([(circle, '') for circle in circles])

        # Check if we have a request pending from this user.
        # If yes, this just becomes accepting a local pending request
        # Else create a friend request that will be pending on the target user
        calls = []
        responseType = "I"
        itemType = "activity"
        cols = yield db.multiget_slice([myKey, targetKey], "entities", ["basic"])
        users = utils.multiSuperColumnsToDict(cols)

        # We have a pending incoming connection.  Accept It.
        try:
            cols = yield db.get(myKey, "pendingConnections", targetKey)
            pendingType = cols.column.value
            if pendingType == '0':
                raise errors.InvalidRequest(_("A similar request is already pending"))

            d1 = db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d2 = db.batch_insert(targetKey, "connections", {myKey: {'__default__':''}})

            #
            # Update name indices
            #
            myName = users[myKey]["basic"].get("name", None)
            myFirstName = users[myKey]["basic"].get("firstname", None)
            myLastName = users[myKey]["basic"].get("lastname", None)
            targetName = users[targetKey]['basic'].get('name', None)
            targetFirstName = users[targetKey]["basic"].get("firstname", None)
            targetLastName = users[targetKey]["basic"].get("lastname", None)

            d3 = utils.updateDisplayNameIndex(targetKey, [myKey], targetName, None)
            d4 = utils.updateDisplayNameIndex(myKey, [targetKey], myName, None)

            mutMap = {}
            for field in ['name', 'firstname', 'lastname']:
                name = users[myKey]["basic"].get(field, None)
                if name:
                    colName = name.lower() + ":" + myKey
                    mutMap.setdefault(targetKey, {}).setdefault('nameIndex', {})[colName]=''
                name = users[targetKey]['basic'].get(field, None)
                if name:
                    colName = name.lower() + ":" + targetKey
                    mutMap.setdefault(myKey, {}).setdefault('nameIndex', {})[colName] = ''
            d5 = db.batch_mutate(mutMap)

            #
            # Add to feeds
            #
            myItemId = utils.getUniqueKey()
            targetItemId = utils.getUniqueKey()
            orgId = users[myKey]["basic"]["org"]
            myItem, attachments = yield utils.createNewItem(request, itemType,
                                                            ownerId=myKey,
                                                            subType="connection",
                                                            ownerOrgId=orgId)
            targetItem, attachments = yield utils.createNewItem(request,
                                                            itemType,
                                                            ownerId=targetKey,
                                                            subType="connection",
                                                            ownerOrgId=orgId)
            targetItem["meta"]["target"] = myKey
            myItem["meta"]["target"] = targetKey
            d6 = db.batch_insert(myItemId, "items", myItem)
            d7 = db.batch_insert(targetItemId, "items", targetItem)

            userItemValue = ":".join([responseType, myItemId,
                                      myItemId, "activity", myKey, ""])
            d8 = db.insert(myKey, "userItems", userItemValue,
                           myItem["meta"]['uuid'])
            userItemValue = ":".join([responseType, targetItemId, targetItemId,
                                      itemType, targetKey, ""])
            d9 = db.insert(targetKey, "userItems", userItemValue,
                           targetItem["meta"]['uuid'])

            # TODO: Push to feeds of friends and followers of both users.
            # TODO: Notify target user about the accepted request.

            calls = [d1, d2, d3, d4, d5, d6, d7, d8, d9]
            calls.append(self._removeFromPending(myKey, targetKey))

        # No incoming connection request.  Send a request to the target users.
        except ttypes.NotFoundException:
            d1 = db.insert(myKey, "pendingConnections", '0', targetKey)
            d2 = db.insert(targetKey, "pendingConnections", '1', myKey)
            d3 = self._notify(myKey, targetKey)
            calls = [d1, d2, d3]

        yield defer.DeferredList(calls)


    @defer.inlineCallbacks
    def _cancelFriendRequest(self, myKey, targetKey):
        yield self._removeFromPending(myKey, targetKey)
        # TODO: UI update


    @defer.inlineCallbacks
    def _archiveFriendRequest(self, myKey, targetKey):
        try:
            cols = yield db.get_slice(myKey, "latest", ["people"])
            cols = utils.supercolumnsToDict(cols)
            for tuuid, key in cols['people'].items():
                if key == targetKey:
                    yield db.remove(myKey, "latest", tuuid, "people")
        except ttypes.NotFoundException:
            pass
        # TODO: UI update


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfriend(self, myKey, targetKey):
        cols = yield db.multiget_slice([myKey, targetKey], "entities",
                                        ["basic"])
        users = utils.multiSuperColumnsToDict(cols)
        targetDisplayName = users[targetKey]["basic"]["name"]
        myDisplayName = users[myKey]["basic"]["name"]
        myFirstName = users[myKey]["basic"].get("firstname", None)
        myLastName = users[myKey]["basic"].get("lastname", None)
        targetFirstName = users[targetKey]["basic"].get("firstname", None)
        targetLastName = users[targetKey]["basic"].get("lastname", None)
        _getColName = lambda name,Id: ":".join([name.lower(), Id])

        mutations = {myKey:{}, targetKey:{}}
        mutations[myKey]["connections"] = {targetKey: None}
        mutations[myKey]["displayNameIndex"] = {_getColName(targetDisplayName, targetKey):None}
        mutations[targetKey]["connections"] = {myKey:None}
        mutations[targetKey]["displayNameIndex"] = {_getColName(myDisplayName, myKey):None}

        if any([myDisplayName, myFirstName, myLastName]):
            mutations[targetKey]["nameIndex"]={}
        if any([targetDisplayName, targetFirstName, targetLastName]):
            mutations[myKey]["nameIndex"] = {}

        for name in [myDisplayName, myFirstName, myLastName]:
            if name:
                colname = _getColName(name, myKey)
                mutations[targetKey]["nameIndex"][colname] = None
        for name in [targetDisplayName, targetFirstName, targetLastName]:
            if name:
                colname = _getColName(name, targetKey)
                mutations[myKey]["nameIndex"][colname] = None

        yield db.batch_mutate(mutations)
        # TODO: delete the notifications and items created while
        # sending&accepting friend request
        yield self._removeFromPending(myKey, targetKey)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)

        # We are setting an empty value to 'cu' here just to make sure that
        # any errors when looking validating the entity should not leave us
        # in a bad state.

        request.addCookie('cu', '', path="/ajax/profile")
        if request.args.get("id", None):
            userKey, ign = yield utils.getValidEntityId(request, "id", "user")
        else:
            userKey = myKey

        # XXX: We should use getValidEntityId to fetch the entire user
        # info instead of another call to the database.
        request.addCookie('cu', userKey, path="/ajax/profile")
        cols = yield db.get_slice(userKey, "entities")
        if cols:
            user = utils.supercolumnsToDict(cols)
            args["user"] = user

        detail = utils.getRequestArg(request, "dt") or "activity"
        args["detail"] = detail
        args["userKey"] = userKey
        args["menuId"] = "people"

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
        if script:
            yield renderScriptBlock(request, "profile.mako", "summary",
                                    landing, "#profile-summary", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_subactions",
                                    landing, "#user-subactions", "set", **args)

        fetchedEntities = set()
        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        if detail == "activity":
            userItems = yield self._getUserItems(request, userKey, start=start)
            args.update(userItems)

        if script:
            yield renderScriptBlock(request, "profile.mako", "tabs", landing,
                                    "#profile-tabs", "set", **args)
            handlers = {} if detail != "activity" \
                else {"onload": "(function(obj){$$.convs.load(obj);})(this);"}

            if fromFetchMore and detail == "activity":
                yield renderScriptBlock(request, "profile.mako", "content", landing,
                                            "#next-load-wrapper", "replace", True,
                                            handlers=handlers, **args)
            else:
                yield renderScriptBlock(request, "profile.mako", "content", landing,
                                        "#profile-content", "set", True,
                                        handlers=handlers, **args)

        # List the user's subscriptions
        cols = yield db.get_slice(userKey, "subscriptions", count=11)
        subscriptions = set(utils.columnsToDict(cols).keys())
        args["subscriptions"] = subscriptions

        # List the user's followers
        cols = yield db.get_slice(userKey, "followers", count=11)
        followers = set(utils.columnsToDict(cols).keys())
        args["followers"] = followers

        # List the user's friends (if allowed and look for common friends)
        cols = yield db.multiget_slice([myKey, userKey], "connections")
        myFriends = set(utils.supercolumnsToDict(cols[myKey]).keys())
        userFriends = set(utils.supercolumnsToDict(cols[userKey]).keys())
        commonFriends = myFriends.intersection(userFriends)
        args["commonFriends"] = commonFriends

        # Fetch item data (name and avatar) for subscriptions, followers,
        # user groups and common items.
        entitiesToFetch = followers.union(subscriptions, commonFriends)\
                                   .difference(fetchedEntities)
        cols = yield db.multiget_slice(entitiesToFetch,
                                       "entities", super_column="basic")
        rawUserData = {}
        for key, data in cols.items():
            if len(data) > 0:
                rawUserData[key] = utils.columnsToDict(data)
        args["rawUserData"] = rawUserData

        # List the user's groups (and look for groups common with me)
        cols = yield db.multiget_slice([myKey, userKey], "entityGroupsMap")
        myGroups = set(utils.columnsToDict(cols[userKey]).keys())
        userGroups = set(utils.columnsToDict(cols[userKey]).keys())
        commonGroups = myGroups.intersection(userGroups)
        if len(userGroups) > 10:
            userGroups = sample(userGroups, 10)
        args["userGroups"] = userGroups
        args["commonGroups"] = commonGroups

        groupsToFetch = commonGroups.union(userGroups)
        cols = yield db.multiget_slice(groupsToFetch, "entities",
                                       super_column="basic")
        rawGroupData = {}
        for key, data in cols.items():
            if len(data) > 0:
                rawGroupData[key] = utils.columnsToDict(data)
        args["rawGroupData"] = rawGroupData

        if script:
            yield renderScriptBlock(request, "profile.mako", "user_subscriptions",
                                    landing, "#user-subscriptions", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_followers",
                                    landing, "#user-followers", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_me",
                                    landing, "#user-me", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "user_groups",
                                    landing, "#user-groups", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "profile.mako", **args)

        request.finish()


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount != 1:
            return self._epilogue(request, defer.fail(errors.NotFoundError()))

        action = request.postpath[0]
        requestDeferred = utils.getValidEntityId(request, "id", "user")
        myKey = request.getSession(IAuthInfo).username

        def callback((targetKey, target)):
            actionDeferred = None
            if action == "friend":
                actionDeferred = self._friend(request, myKey, targetKey)
            elif action == "unfriend":
                actionDeferred = self._unfriend(myKey, targetKey)
            elif action == "follow":
                actionDeferred = self._follow(myKey, targetKey)
            elif action == "unfollow":
                actionDeferred = self._unfollow(myKey, targetKey)
            else:
                raise errors.NotFoundError()

            relation = Relation(myKey, [targetKey])
            data = {"relations": relation}
            def fetchRelations(ign):
                return defer.DeferredList([relation.initFriendsList(),
                                           relation.initPendingList(),
                                           relation.initSubscriptionsList()])

            isProfile = (utils.getRequestArg(request, "_pg") == "/profile")
            isFeed =    (utils.getRequestArg(request, "_pg")  == "/feed")
            isPeople =  (utils.getRequestArg(request, "_pg")  == "/people")
            def renderActions(ign):
                def renderLatestCounts(ign):
                    return utils.render_LatestCounts(request, False)

                if not isFeed:
                    d = renderScriptBlock(request, "profile.mako", "user_actions",
                                    False, "#user-actions-%s"%targetKey, "set",
                                    args=[targetKey, True], **data)
                    if isProfile:
                        def renderSubactions(ign):
                            return renderScriptBlock(request, "profile.mako",
                                        "user_subactions", False,
                                        "#user-subactions-%s"%targetKey, "set",
                                        args=[targetKey, False], **data)
                        d.addCallback(renderSubactions)
                    if isPeople:
                        def updatePendingRequestsCount(ign):
                            def _update_count(counts):
                                pendingRequestCount = counts['people'] if counts.get('people', 0)!= 0 else ''
                                request.write("$('#pending-requests-count').html('%s');"%(pendingRequestCount))
                            d02 = utils.getLatestCounts(request, False)
                            d02.addCallback(_update_count)
                            return d02
                        d.addCallback(updatePendingRequestsCount)
                    d.addCallback(renderLatestCounts)
                    return d
                else:
                    # if action == "friend" it is possible that user has accepted
                    # friend request through suggestions. so update the counts.
                    d = people.get_suggestions(request, constants.SUGGESTION_PER_PAGE, mini=True)
                    def renderSuggestion(res):
                        suggestions, entities = res
                        return renderScriptBlock(request, "feed.mako", "_suggestions",
                                                 False, "#suggestions", "set", True,
                                                 relations = relation,
                                                 suggestions = suggestions,
                                                 entities=entities)
                    d.addCallback(renderSuggestion)
                    if action == "friend":
                        d.addCallback(renderLatestCounts)
                    return d

            actionDeferred.addCallback(fetchRelations)
            actionDeferred.addCallback(renderActions)
            return actionDeferred

        requestDeferred.addCallback(callback)
        return self._epilogue(request, requestDeferred)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)

        return self._epilogue(request, d)
