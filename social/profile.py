import PythonMagick
import imghdr
from random                 import sample

from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social                 import Db, auth, utils, base, plugins, _, __
from social                 import constants, feed
from social.logging         import dump_args, profile
from social.isocial         import IAuthInfo

@defer.inlineCallbacks
def deleteAvatarItem(entity, isLogo=False):
    entity = yield Db.get_slice(entity, "entities", ["basic"])
    entity = utils.supercolumnsToDict(entity)
    itemId = None
    imgFmt = None
    col = None
    if isLogo:
        col = entity["basic"].get("logo", None)
    else:
        col = entity["basic"].get("avatar", None)
    if col:
        imgFmt, itemId = col.split(":")
    if itemId:
        yield Db.remove(itemId, "items")

@profile
@defer.inlineCallbacks
@dump_args
def saveAvatarItem(entityId, data, isLogo=False):
    imageFormat = _getImageFileFormat(data)
    if imageFormat not in constants.SUPPORTED_IMAGE_TYPES:
        raise errors.UnsupportedFileType()

    try:
        original = PythonMagick.Blob(data)
        image = PythonMagick.Image(original)
    except Exception as e:
        raise errors.UnknownFileFormat()

    medium = PythonMagick.Blob()
    small = PythonMagick.Blob()
    large = PythonMagick.Blob()
    largesize = constants.LOGO_SIZE_LARGE if isLogo else constants.AVATAR_SIZE_LARGE
    mediumsize = constants.LOGO_SIZE_MEDIUM if isLogo else constants.AVATAR_SIZE_MEDIUM
    smallsize = constants.LOGO_SIZE_SMALL if isLogo else constants.AVATAR_SIZE_SMALL
    log.msg(largesize, smallsize, mediumsize)

    image.scale(largesize)
    image.write(large)
    image.scale(mediumsize)
    image.write(medium)
    image.scale(smallsize)
    image.write(small)

    itemId = utils.getUniqueKey()
    item = {
        "meta": {"owner": entityId, "acl": "company", "type": "image"},
        "avatar": {
            "format": imageFormat,
            "small": small.data, "medium": medium.data,
            "large": large.data, "original": original.data
        }}
    yield Db.batch_insert(itemId, "items", item)
    #delete older image if any;
    yield deleteAvatarItem(entityId, isLogo)

    defer.returnValue("%s:%s" % (imageFormat, itemId))


@profile
@dump_args
def _getImageFileFormat(data):
    imageType = imghdr.what(None, data)
    if imageType:
        return imageType.lower()
    return imageType


class ProfileResource(base.BaseResource):
    isLeaf = True
    resources = {}

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
        nextPageStart = None
        args = {"myKey": myKey}

        relation = Relation(myKey, [])
        yield defer.DeferredList([relation.initFriendsList(),
                                  relation.initGroupsList()])

        toFetchEntities.add(userKey)
        while len(convs) < count:
            cols = yield Db.get_slice(userKey, "userItems", start = toFetchStart,
                                      reverse=True, count=toFetchCount)
            fetchedUserItem.extend(cols[0:count])
            if len(cols):
                toFetchStart = cols[-1].column.name
            else:
                toFetchStart = ''
            if len(cols) == toFetchCount:
                nextPageStart = toFetchStart
            else:
                nextPageStart = None

            for col in cols:
                value = tuple(col.column.value.split(":"))
                rtype, itemId, convId, convType, convOwnerId, commentSnippet = value
                convs.append(convId)
            if len(cols) == toFetchCount:
                convs = convs[0:count]

            items = yield Db.multiget_slice(convs, "items", ["meta"])
            items = utils.multiSuperColumnsToDict(items)
            for convId in convs[:]:
                    acl = items[convId]["meta"]["acl"]
                    owner = items[convId]["meta"]["owner"]

                    if not utils.checkAcl(myKey, acl, owner, relation, myOrgId):
                        convs.remove(convId)
            if len(cols) < toFetchCount:
                break
        if nextPageStart:
            nextPageStart = utils.encodeKey(nextPageStart)

        for col in fetchedUserItem:
            value = tuple(col.column.value.split(":"))
            rtype, itemId, convId, convType, convOwnerId, commentSnippet = value
            if convId not in convs:
                continue
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
                    toFetchEntities.add(userKey_)

        items = yield Db.multiget_slice(toFetchItems, "items", ["meta", "tags"])
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

        fetchedEntities = yield Db.multiget(toFetchEntities, "entities", "basic")
        entities = utils.multiSuperColumnsToDict(fetchedEntities)

        tags = {}
        if toFetchTags:
            userOrgId = entities[userKey]["basic"]["org"]
            fetchedTags = yield Db.get_slice(userOrgId, "orgTags", toFetchTags)
            tags = utils.supercolumnsToDict(fetchedTags)

        fetchedLikes = yield Db.multiget(toFetchItems, "itemLikes", myKey)
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
        d1 = Db.insert(myKey, "subscriptions", "", targetKey)
        d2 = Db.insert(targetKey, "followers", "", myKey)
        yield d1
        yield d2


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfollow(self, myKey, targetKey):
        d1 = Db.remove(myKey, "subscriptions", targetKey)
        d2 = Db.remove(targetKey, "followers", myKey)
        yield d1
        yield d2


    @profile
    @defer.inlineCallbacks
    @dump_args
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
            cols = yield Db.multiget_slice([myKey, targetKey], "entities",
                                            ["basic"])
            users = utils.multiSuperColumnsToDict(cols)
            d1 = Db.remove(myKey, "pendingConnections", targetKey)
            d2 = Db.remove(targetKey, "pendingConnections", myKey)
            d3 = Db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d4 = Db.batch_insert(targetKey, "connections", {myKey: {'__default__':''}})

            myName = users[myKey]["basic"].get("name", None)
            myFirstName = users[myKey]["basic"].get("firstname", None)
            myLastName = users[myKey]["basic"].get("lastname", None)
            targetName = users[targetKey]['basic'].get('name', None)
            targetFirstName = users[targetKey]["basic"].get("firstname", None)
            targetLastName = users[targetKey]["basic"].get("lastname", None)

            d5 = utils._updateDisplayNameIndex(targetKey, myKey, targetName, None)
            d6 = utils._updateDisplayNameIndex(myKey, targetKey, myName, None)

            d7 = utils._updateNameIndex(myKey, targetKey,  myName, None)
            d8 = utils._updateNameIndex(myKey, targetKey, myFirstName, None)
            d9 = utils._updateNameIndex(myKey,targetKey,  myLastName, None)

            d10 = utils._updateNameIndex(targetKey, myKey, targetName, None)
            d11 = utils._updateNameIndex(targetKey, myKey, targetFirstName, None)
            d12 = utils._updateNameIndex(targetKey, myKey, targetLastName, None)

            #add to feed
            responseType = "I"
            itemType = "activity"
            myItemId = utils.getUniqueKey()
            targetItemId = utils.getUniqueKey()
            myItem = utils.createNewItem(request, itemType, ownerId = myKey,
                                         subType="connection",
                                         ownerOrgId= users[myKey]["basic"]["org"])
            targetItem = utils.createNewItem(request, itemType,
                                             ownerId= targetKey,
                                             subType="connection",
                                             ownerOrgId = users[targetKey]["basic"]["org"])
            targetItem["meta"]["target"] = myKey
            myItem["meta"]["target"] = targetKey
            d13 = Db.batch_insert(myItemId, "items", myItem)
            d14 = Db.batch_insert(targetItemId, "items", targetItem)
            d15 = feed.pushToFeed(myKey, myItem["meta"]["uuid"], myItemId,
                                  myItemId, responseType, itemType, myKey)
            d16 = feed.pushToFeed(targetKey, targetItem["meta"]["uuid"],
                                  targetItemId, targetItemId, responseType,
                                  itemType, targetKey)

            userItemValue = ":".join([responseType, myItemId,
                                      myItemId, "activity", myKey, ""])
            d17 =  Db.insert(myKey, "userItems", userItemValue,
                             myItem["meta"]['uuid'])
            userItemValue = ":".join([responseType, targetItemId, targetItemId,
                                      itemType, targetKey, ""])
            d18 =  Db.insert(targetKey, "userItems", userItemValue,
                             targetItem["meta"]['uuid'])
            #notify users

            calls = [d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12, d13,
                     d14, d15, d16, d17, d18]
        except ttypes.NotFoundException:
            d1 = Db.insert(myKey, "pendingConnections", '0', targetKey)
            d2 = Db.insert(targetKey, "pendingConnections", '1', myKey)
            calls = [d1, d2]

        yield defer.DeferredList(calls)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _unfriend(self, myKey, targetKey):

        cols = yield Db.multiget_slice([myKey, targetKey], "entities",
                                        ["basic"])
        users = utils.multiSuperColumnsToDict(cols)
        targetDisplayName = users[targetKey]["basic"]["name"]
        myDisplayName = users[myKey]["basic"]["name"]
        myFirstName = users[myKey]["basic"].get("firstname", None)
        myLastName = users[myKey]["basic"].get("lastname", None)
        targetFirstName = users[targetKey]["basic"].get("firstname", None)
        targetLastName = users[targetKey]["basic"].get("lastname", None)

        deferreds = [Db.remove(myKey, "connections", None, targetKey),
                     Db.remove(targetKey, "connections", None, myKey),
                     Db.remove(myKey, "pendingConnections", targetKey),
                     Db.remove(targetKey, "pendingConnections", myKey),
                     Db.remove(myKey, "displayNameIndex",
                               ":".join([targetDisplayName, targetKey])),
                     Db.remove(targetKey, "displayNameIndex",
                               ":".join([myDisplayName, myKey]))]
        if myFirstName:
            deferreds.append(utils.deleteNameIndex(targetKey, myFirstName, myKey))
        if myLastName:
            deferreds.append(utils.deleteNameIndex(targetKey, myLastName, myKey))

        if targetFirstName:
            deferreds.append(utils.deleteNameIndex(myKey, targetFirstName, targetKey))
        if targetLastName:
            deferreds.append(utils.deleteNameIndex(myKey, targetLastName, targetKey))

        yield defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def _changePassword(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        curr_passwd = utils.getRequestArg(request, "curr_passwd")
        passwd1 = utils.getRequestArg(request, "passwd1")
        passwd2 = utils.getRequestArg(request, "passwd2")


        yield self._renderEditProfile(request)

        args["errorMsg"] = ""
        if not curr_passwd:
            args["errorMsg"] = "Enter current password"
        if passwd1 != passwd2:
            args["errorMsg"] = "New password didn't match"
        cols = yield Db.get(myKey, "entities", "emailId", "basic")
        emailId = cols.column.value
        col = yield Db.get(emailId, "userAuth", "passwordHash")
        passwdHash = col.column.value
        if curr_passwd and passwdHash != utils.md5(curr_passwd):
            args["errorMsg"] ="Incorrect Password"

        if args["errorMsg"]:
            yield renderScriptBlock(request, "profile.mako", "changePasswd",
                                    landing, "#profile-content", "set", **args)
        else:
            newPasswd = utils.md5(passwd1)
            yield Db.insert(emailId, "userAuth", newPasswd, "passwordHash")
            args["errorMsg"] = "password changed successfully"
            yield renderScriptBlock(request, "profile.mako", "changePasswd",
                                    landing, "#profile-content", "set", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _edit(self, request):

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        userInfo = {}
        calls = []


        for cn in ("jobTitle", "location", "desc", "name", "firstname", "lastname"):
            val = utils.getRequestArg(request, cn)
            if val:
                userInfo.setdefault("basic", {})[cn] = val

        user = yield Db.get_slice(myKey, "entities", ["basic"])
        user = utils.supercolumnsToDict(user)

        cols = yield Db.get_slice(myKey, 'connections', )
        friends = [item.super_column.name for item in cols] + [args["orgKey"]]

        for field in ["name", "lastname", "firstname"]:
            if "basic" in userInfo and field in userInfo["basic"]:
                d = utils.updateNameIndex(myKey, friends,
                                          userInfo["basic"][field],
                                          user["basic"].get(field, None))
                if field == 'name':
                    d1 = utils.updateDisplayNameIndex(myKey, friends,
                                                userInfo["basic"][field],
                                                user["basic"].get(field, None))
                    calls.append(d1)
                calls.append(d)

        if calls:
            yield defer.DeferredList(calls)


        if "basic" in userInfo:
            basic_acl = utils.getRequestArg(request, "basic_acl") or 'public'
            userInfo["basic"]["acl"] = basic_acl

        dp = utils.getRequestArg(request, "dp")
        if dp:
            avatar = yield saveAvatarItem(myKey, dp)
            if not userInfo.has_key("basic"):
                userInfo["basic"] = {}
            userInfo["basic"]["avatar"] = avatar

        expertise = utils.getRequestArg(request, "expertise")
        expertise_acl = utils.getRequestArg(request, "expertise_acl") or 'public'
        if expertise:
            userInfo["expertise"] = {}
            userInfo["expertise"][expertise]=""
            userInfo["expertise"]["acl"]=expertise_acl

        language = utils.getRequestArg(request, "language")
        lr = utils.getRequestArg(request, "language_r") == "on"
        ls = utils.getRequestArg(request, "language_s") == "on"
        lw = utils.getRequestArg(request, "language_w") == "on"
        language_acl = utils.getRequestArg(request, "language_acl") or 'public'
        if language:
            userInfo["languages"]= {}
            userInfo["languages"][language]= "%(lr)s/%(lw)s/%(ls)s" %(locals())
            userInfo["languages"]["acl"] = language_acl

        c_email = utils.getRequestArg(request, "c_email")
        c_im = utils.getRequestArg(request, "c_im")
        c_phone = utils.getRequestArg(request, "c_phone")
        c_mobile = utils.getRequestArg(request, "c_phone")
        contacts_acl = utils.getRequestArg(request, "contacts_acl") or 'public'

        if any([c_email, c_im, c_phone]):
            userInfo["contact"] = {}
            userInfo["contact"]["acl"] = contacts_acl

        if c_email:
            userInfo["contact"]["mail"] = c_email
        if c_im:
            userInfo["contact"]["im"] = c_im
        if c_phone:
            userInfo["contact"]["phone"] = c_phone


        interests = utils.getRequestArg(request, "interests")
        interests_acl = utils.getRequestArg(request, "interests_acl") or 'public'
        if interests:
            userInfo["interests"]= {}
            userInfo["interests"][interests]= interests
            userInfo["interests"]["acl"] = interests_acl

        p_email = utils.getRequestArg(request, "p_email")
        p_phone = utils.getRequestArg(request, "p_phone")
        p_mobile = utils.getRequestArg(request, "p_mobile")
        dob_day = utils.getRequestArg(request, "dob_day")
        dob_mon = utils.getRequestArg(request, "dob_mon")
        dob_year = utils.getRequestArg(request, "dob_year")
        hometown = utils.getRequestArg(request, "hometown")
        currentCity = utils.getRequestArg(request, "currentCity")
        personal_acl = utils.getRequestArg(request, "personal_acl") or 'public'
        if any([p_email, p_phone, hometown, currentCity,]) \
            or all([dob_year, dob_mon, dob_day]):
            userInfo["personal"]={}
        if p_email:
            userInfo["personal"]["email"] = p_email
        if p_phone:
            userInfo["personal"]["phone"] = p_phone
        if hometown:
            userInfo["personal"]["hometown"] = hometown
        if currentCity:
            userInfo["personal"]["currentCity"] = currentCity
        if dob_day and dob_mon and dob_year:
            userInfo["personal"]["birthday"] = "%s%s%s"%(dob_year, dob_mon, dob_day)

        employer = utils.getRequestArg(request, "employer")
        emp_start = utils.getRequestArg(request, "emp_start") or ''
        emp_end = utils.getRequestArg(request, "emp_end") or ''
        emp_title = utils.getRequestArg(request, "emp_title") or ''
        emp_desc = utils.getRequestArg(request, "emp_desc") or ''

        if employer:
            userInfo["employers"] = {}
            key = "%s:%s:%s:%s" %(emp_end, emp_start, employer, emp_title)
            userInfo["employers"][key] = emp_desc

        college = utils.getRequestArg(request, "college")
        degree = utils.getRequestArg(request, "degree") or ''
        edu_end = utils.getRequestArg(request, "edu_end") or ''
        if college:
            userInfo["education"] = {}
            key = "%s:%s" %(edu_end, college)
            userInfo["education"][key] = degree

        if userInfo:
            yield Db.batch_insert(myKey, "entities", userInfo)
        request.redirect("/profile/edit")


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount != 1:
                raise errors.InvalidRequest()

        action = request.postpath[0]
        if action in ( "edit", "changePasswd") :
            headers = request.requestHeaders
            content_length = headers.getRawHeaders("content-length", [0])[0]
            if int(content_length) > constants.MAX_IMAGE_SIZE:
                raise errors.LargeFile()
            if action == "edit":
                requestDeferred = self._edit(request)
            elif action == "changePasswd":
                requestDeferred = self._changePassword(request)
            return self._epilogue(request, requestDeferred)

        requestDeferred = utils.getValidEntityId(request, "id", "user")
        myKey = auth.getMyKey(request)

        def callback(targetKey):
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
                                args=[targetKey, not isProfile], **data)
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


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1 and request.postpath[0] == 'edit':
            d = self._renderEditProfile(request)
        elif segmentCount == 1 and request.postpath[0] == 'changePasswd':
            d = self._changePassword(request)

        return self._epilogue(request, d)


    @profile
    @defer.inlineCallbacks
    @dump_args
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
        elif detail == "detail":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editDetail",
                                    landing, "#profile-content", "set", **args)
        elif detail == "passwd":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "changePasswd",
                                    landing, "#profile-content", "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
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

        fetchedEntities = set()
        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        if detail == "notes":
            userItems = yield self._getUserItems(request, userKey, start=start)
            args.update(userItems)


        if script:
            yield renderScriptBlock(request, "profile.mako", "tabs", landing,
                                    "#profile-tabs", "set", **args)
            handlers = {} if detail != "notes" \
                else {"onload": "(function(obj){$$.convs.load(obj);})(this);"}

            if fromFetchMore and detail == "notes":
                yield renderScriptBlock(request, "profile.mako", "content", landing,
                                            "#next-load-wrapper", "replace", True,
                                            handlers=handlers, **args)
            else:
                yield renderScriptBlock(request, "profile.mako", "content", landing,
                                        "#profile-content", "set", True,
                                        handlers=handlers, **args)

        if newId or not script:
            # List the user's subscriptions
            cols = yield Db.get_slice(userKey, "subscriptions", count=11)
            subscriptions = set(utils.columnsToDict(cols).keys())
            args["subscriptions"] = subscriptions

            # List the user's followers
            cols = yield Db.get_slice(userKey, "followers", count=11)
            followers = set(utils.columnsToDict(cols).keys())
            args["followers"] = followers

            # List the user's friends (if allowed and look for common friends)
            cols = yield Db.multiget_slice([myKey, userKey], "connections")
            myFriends = set(utils.supercolumnsToDict(cols[myKey]).keys())
            userFriends = set(utils.supercolumnsToDict(cols[userKey]).keys())
            commonFriends = myFriends.intersection(userFriends)
            args["commonFriends"] = commonFriends

            # Fetch item data (name and avatar) for subscriptions, followers,
            # user groups and common items.
            entitiesToFetch = followers.union(subscriptions, commonFriends)\
                                       .difference(fetchedEntities)
            cols = yield Db.multiget_slice(entitiesToFetch,
                                           "entities", super_column="basic")
            rawUserData = {}
            for key, data in cols.items():
                if len(data) > 0:
                    rawUserData[key] = utils.columnsToDict(data)
            args["rawUserData"] = rawUserData

            # List the user's groups (and look for groups common with me)
            cols = yield Db.multiget_slice([myKey, userKey], "userGroups")
            myGroups = set(utils.columnsToDict(cols[userKey]).keys())
            userGroups = set(utils.columnsToDict(cols[userKey]).keys())
            commonGroups = myGroups.intersection(userGroups)
            if len(userGroups) > 10:
                userGroups = sample(userGroups, 10)
            args["userGroups"] = userGroups
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
            yield renderScriptBlock(request, "profile.mako", "user_groups",
                                    landing, "#user-groups", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "profile.mako", **args)

        request.finish()
