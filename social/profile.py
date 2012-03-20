import uuid
from random                 import sample

from twisted.web            import resource, server, http
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social                 import db, utils, base, plugins, _, __
from social                 import constants, feed, errors, people
from social                 import notifications, files, config
from social                 import template as t
from social.relations       import Relation
from social.logging         import dump_args, profile, log
from social.isocial         import IAuthInfo


class ProfileResource(base.BaseResource):
    isLeaf = True
    _templates = ['emails.mako', 'profile.mako', 'feed.mako']
    resources = {}


    @defer.inlineCallbacks
    def _removeNotification(self, entityId, targetId):
        cols = yield db.get_slice(entityId, "latest", ['people'])
        cols = utils.supercolumnsToDict(cols)
        for tuuid, key in cols.get('people', {}).items():
            if key == targetId:
                yield db.remove(entityId, "latest", tuuid, 'people')

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _getUserItems(self, request, userId, start='', count=10):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
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
        timestamps = {}
        items = {}
        nextPageStart = None
        args = {'myId': myId}

        relation = Relation(myId, [])
        yield relation.initGroupsList()

        toFetchEntities.add(userId)

        while len(convs) < toFetchCount:
            cols = yield db.get_slice(userId, "userItems", start=toFetchStart,
                                      reverse=True, count=toFetchCount)
            tmpIds = []
            for col in cols:
                convId = col.column.value.split(":")[2]
                if convId not in tmpIds and convId not in convs:
                    tmpIds.append(convId)
            (filteredConvs, deletedConvs) = yield utils.fetchAndFilterConvs\
                                        (tmpIds, relation, items, myId, myOrgId)
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
            timestamps[value] = col.column.timestamp/1e6
            rtype, itemId, convId, convType, convOwnerId, commentSnippet = value
            commentSnippet = """<span class="snippet">"%s"</span>""" %(_(commentSnippet))
            toFetchEntities.add(convOwnerId)
            if rtype == 'I':
                toFetchItems.add(convId)
                toFetchResponses.add(convId)
                userItems.append(value)
            elif rtype == "L" and itemId == convId and convOwnerId != userId:
                reasonStr[value] = _("liked %s's %s")
                userItems.append(value)
            elif rtype == "L"  and convOwnerId != userId:
                r = "answer" if convType == 'question' else 'comment'
                reasonStr[value] = _("liked") + " %s " %(commentSnippet) + _("%s "%r) + _("on %s's %s")
                userItems.append(value)
            elif rtype in ["C", 'Q'] and convOwnerId != userId:
                reasonStr[value] = "%s"%(commentSnippet) + _(" on %s's %s")
                userItems.append(value)

        itemResponses = yield db.multiget_slice(toFetchResponses, "itemResponses",
                                                count=2, reverse=True)
        for convId, comments in itemResponses.items():
            responses[convId] = []
            for comment in comments:
                userId_, itemKey = comment.column.value.split(':')
                if itemKey not in toFetchItems:
                    responses[convId].insert(0,itemKey)
                    toFetchItems.add(itemKey)
                    toFetchEntities.add(userId_)

        items = yield db.multiget_slice(toFetchItems, "items", ["meta", "tags", "attachments"])
        items = utils.multiSuperColumnsToDict(items)
        args["items"] = items
        extraDataDeferreds = []

        for convId in convs:
            if convId not in items:
                continue

            meta = items[convId]["meta"]
            itemType = meta["type"]
            toFetchEntities.add(meta["owner"])
            if "target" in meta:
                toFetchEntities.update(meta["target"].split(','))

            toFetchTags.update(items[convId].get("tags", {}).keys())

            if itemType in plugins:
                d =  plugins[itemType].fetchData(args, convId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchEntities.update(ret)

        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()

        tags = {}
        if toFetchTags:
            userOrgId = entities[userId].basic["org"]
            fetchedTags = yield db.get_slice(userOrgId, "orgTags", toFetchTags)
            tags = utils.supercolumnsToDict(fetchedTags)

        fetchedLikes = yield db.multiget(toFetchItems, "itemLikes", myId)
        myLikes = utils.multiColumnsToDict(fetchedLikes)

        data = {"entities": entities, "reasonStr": reasonStr,
                "tags": tags, "myLikes": myLikes, "userItems": userItems,
                "responses": responses, "nextPageStart": nextPageStart,
                "timestamps": timestamps }
        del args['myId']
        args.update(data)
        defer.returnValue(args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _follow(self, myId, targetId):
        d1 = db.insert(myId, "subscriptions", "", targetId)
        d2 = db.insert(targetId, "followers", "", myId)
        entities = base.EntitySet([myId, targetId])
        d3 = entities.fetchData()
        def notifyFollow(res):
            data = {'entities': entities}
            return notifications.notify([targetId], ":NF", myId, **data)
        d3.addCallback(notifyFollow)

        yield defer.DeferredList([d1, d2, d3])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, myId, targetId):
        d1 = db.remove(myId, "subscriptions", targetId)
        d2 = db.remove(targetId, "followers", myId)
        yield defer.DeferredList([d1, d2])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _reportUser(self, request, myId, targetId):

        entities = base.EntitySet([myId, targetId])
        yield entities.fetchData()
        reportedBy = entities[myId].basic["name"]
        email = entities[targetId].basic["emailId"]
        rootUrl = config.get('General', 'URL')
        brandName = config.get('Branding', 'Name')
        authinfo = request.getSession(IAuthInfo)
        amIAdmin = authinfo.isAdmin

        cols = yield db.get_slice(email, "userAuth", ["reactivateToken",
                                                      "isFlagged", "isAdmin"])
        cols = utils.columnsToDict(cols)
        if cols.has_key("isAdmin") and not amIAdmin:
            raise errors.PermissionDenied("Only administrators can flag other \
                                            administrators for verification")

        if cols.has_key("isFlagged"):
            token = cols.get("reactivateToken")
        else:
            token = utils.getRandomKey()
            yield db.insert(email, "userAuth", token, 'reactivateToken')
            yield db.insert(email, "userAuth", "", 'isFlagged')

        body = "%(reportedBy)s has flagged your account for verification."\
               "You can verify your account by clicking on the link below.\n"\
               "\n\n%(reactivateUrl)s\n\n"

        reactivateUrl = "%(rootUrl)s/password/verify?email=%(email)s&token=%(token)s"%(locals())
        args = {"brandName": brandName, "rootUrl": rootUrl,
                "reportedBy":reportedBy, "reactivateUrl": reactivateUrl}
        subject = "[%(brandName)s] Your profile has been flagged for review" %(locals())
        htmlBody = t.getBlock("emails.mako", "reportUser", **args)
        textBody = body %(locals())

        yield utils.sendmail(email, subject, textBody, htmlBody)

        request.write('$$.alerts.info("%s");' % _('User has been flagged for verification'))

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        # We are setting an empty value to 'cu' here just to make sure that
        # any errors when looking validating the entity should not leave us
        # in a bad state.

        request.addCookie('cu', '', path="/ajax/profile")
        if request.args.get("id", None):
            userId, ign = yield utils.getValidEntityId(request, "id", "user")
        else:
            userId = myId

        # XXX: We should use getValidEntityId to fetch the entire user
        # info instead of another call to the database.
        request.addCookie('cu', userId, path="/ajax/profile")
        user = base.Entity(userId)
        yield user.fetchData([])
        if user._data:
            args['user'] = user

        detail = utils.getRequestArg(request, "dt") or "activity"
        args["detail"] = detail
        args["userId"] = userId
        args["menuId"] = "people"
        args['entities'] = {myId: args['me'], userId: user}

        # When scripts are enabled, updates are sent to the page as
        # and when we get the required data from the database.

        # When we are the landing page, we also render the page header
        # and all updates are wrapped in <script> blocks.
        landing = not self._ajax

        # User entered the URL directly
        # Render the header.  Other things will follow.
        if script and landing:
            t.render(request, "profile.mako", **args)

        # Start with displaying the template and navigation menu
        if script and appchange:
            t.renderScriptBlock(request, "profile.mako", "layout",
                                landing, "#mainbar", "set", **args)

        # Prefetch some data about how I am related to the user.
        # This is required in order to reliably filter our profile details
        # that I don't have access to.
        relation = Relation(myId, [userId])
        args["relations"] = relation
        yield defer.DeferredList([relation.initSubscriptionsList(),
                                  relation.initGroupsList()])

        # Reload all user-depended blocks if the currently displayed user is
        # not the same as the user for which new data is being requested.
        if script:
            t.renderScriptBlock(request, "profile.mako", "summary",
                                landing, "#profile-summary", "set", **args)
            t.renderScriptBlock(request, "profile.mako", "user_subactions",
                                landing, "#user-subactions", "set", **args)

        fetchedEntities = set()
        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        if detail == "activity":
            userItems = yield self._getUserItems(request, userId, start=start)
            args.update(userItems)
        elif detail == 'files':
            end = utils.getRequestArg(request, "end") or ''
            end = utils.decodeKey(end)
            start = utils.decodeKey(start)
            userFiles = yield files.userFiles(myId, userId, args['orgId'], start, end, fromFeed=False)
            args['userfiles'] = userFiles
            args['fromProfile'] = True

        if script:
            t.renderScriptBlock(request, "profile.mako", "tabs", landing,
                                "#profile-tabs", "set", **args)
            handlers = {} if detail != "activity" \
                else {"onload": "(function(obj){$$.convs.load(obj);})(this);"}

            if fromFetchMore and detail == "activity":
                t.renderScriptBlock(request, "profile.mako", "content", landing,
                                    "#next-load-wrapper", "replace", True,
                                    handlers=handlers, **args)
            else:
                t.renderScriptBlock(request, "profile.mako", "content", landing,
                                    "#profile-content", "set", True,
                                    handlers=handlers, **args)

        # List the user's subscriptions
        cols = yield db.get_slice(userId, "subscriptions", count=11)
        subscriptions = set(utils.columnsToDict(cols).keys())
        args["subscriptions"] = subscriptions

        # List the user's followers
        cols = yield db.get_slice(userId, "followers", count=11)
        followers = set(utils.columnsToDict(cols).keys())
        args["followers"] = followers

        # Fetch item data (name and avatar) for subscriptions, followers,
        # user groups and common items.
        entitiesToFetch = followers.union(subscriptions)\
                                   .difference(fetchedEntities)

        # List the user's groups (and look for groups common with me)
        cols = yield db.multiget_slice([myId, userId], "entityGroupsMap")
        myGroups = set([x.column.name.split(':', 1)[1] for x in cols[myId]])
        userGroups = set([x.column.name.split(':', 1)[1] for x in cols[userId]])
        commonGroups = myGroups.intersection(userGroups)
        if len(userGroups) > 10:
            userGroups = sample(userGroups, 10)
        args["userGroups"] = userGroups
        args["commonGroups"] = commonGroups

        groupsToFetch = commonGroups.union(userGroups)
        entitiesToFetch = entitiesToFetch.union(groupsToFetch)
        entities = base.EntitySet(entitiesToFetch)
        yield entities.fetchData()
        for entityId, entity in entities.items():
            if not entity._data:
               del entities[entityId]
        args["entities"] = entities

        if script:
            t.renderScriptBlock(request, "profile.mako", "user_subscriptions",
                                landing, "#user-subscriptions", "set", **args)
            t.renderScriptBlock(request, "profile.mako", "user_followers",
                                landing, "#user-followers", "set", **args)
            t.renderScriptBlock(request, "profile.mako", "user_me",
                                landing, "#user-me", "set", **args)
            t.renderScriptBlock(request, "profile.mako", "user_groups",
                                landing, "#user-groups", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            t.render(request, "profile.mako", **args)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount != 1:
            return self._epilogue(request, defer.fail(errors.NotFoundError()))

        action = request.postpath[0]
        requestDeferred = utils.getValidEntityId(request, "id", "user")
        myId = request.getSession(IAuthInfo).username

        def callback((targetId, target)):
            actionDeferred = None
            if action == "follow":
                actionDeferred = self._follow(myId, targetId)
            elif action == "unfollow":
                actionDeferred = self._unfollow(myId, targetId)
            elif action == "report":
                actionDeferred = self._reportUser(request, myId, targetId)
            else:
                raise errors.NotFoundError()

            relation = Relation(myId, [targetId])
            data = {"relations": relation}
            def fetchRelations(ign):
                return relation.initSubscriptionsList()

            isProfile = (utils.getRequestArg(request, "_pg") == "/profile")
            isFeed =    (utils.getRequestArg(request, "_pg") == "/feed")
            isPeople =  (utils.getRequestArg(request, "_pg") == "/people")
            def renderActions(ign):
                if isFeed:
                    d = people.get_suggestions(request, constants.SUGGESTION_PER_PAGE, mini=True)
                    def renderSuggestion(res):
                        suggestions, entities = res
                        t.renderScriptBlock(request, "feed.mako", "_suggestions",
                                            False, "#suggestions", "set", True,
                                            relations = relation,
                                            suggestions = suggestions,
                                            entities=entities)
                    d.addCallback(renderSuggestion)
                    return d
                else:
                    t.renderScriptBlock(request, "profile.mako", "user_actions",
                                        False, "#user-actions-%s"%targetId, "set",
                                        args=[targetId, True], **data)
                    return defer.succeed([])

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
