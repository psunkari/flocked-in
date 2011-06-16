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
from social                 import constants, feed, errors
from social.logging         import dump_args, profile
from social.isocial         import IAuthInfo

@defer.inlineCallbacks
def deleteAvatarItem(entity, isLogo=False):
    entity = yield db.get_slice(entity, "entities", ["basic"])
    entity = utils.supercolumnsToDict(entity)
    itemId = None
    imgFmt = None
    col = None
    if not entity:
        defer.returnValue(None)
    if isLogo:
        col = entity["basic"].get("logo", None)
    else:
        col = entity["basic"].get("avatar", None)
    if col:
        imgFmt, itemId = col.split(":")
    if itemId:
        yield db.remove(itemId, "items")

@profile
@defer.inlineCallbacks
@dump_args
def saveAvatarItem(entityId, data, isLogo=False):
    imageFormat = _getImageFileFormat(data)
    if imageFormat not in constants.SUPPORTED_IMAGE_TYPES:
        raise errors.UnknownFileFormat()

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
    yield db.batch_insert(itemId, "items", item)
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
            cols = yield db.get_slice(userKey, "userItems", start = toFetchStart,
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

            items = yield db.multiget_slice(convs, "items", ["meta"])
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
        cols = yield db.multiget_slice([myKey, targetKey], "entities",
                                            ["basic"])
        users = utils.multiSuperColumnsToDict(cols)
        try:
            cols = yield db.get(myKey, "pendingConnections", targetKey)
            pendingType = cols.column.value
            if pendingType == '0':
                raise errors.PendingRequest()

            d1 = db.remove(myKey, "pendingConnections", targetKey)
            d2 = db.remove(targetKey, "pendingConnections", myKey)
            d3 = db.batch_insert(myKey, "connections", {targetKey: circlesMap})
            d4 = db.batch_insert(targetKey, "connections", {myKey: {'__default__':''}})

            myName = users[myKey]["basic"].get("name", None)
            myFirstName = users[myKey]["basic"].get("firstname", None)
            myLastName = users[myKey]["basic"].get("lastname", None)
            targetName = users[targetKey]['basic'].get('name', None)
            targetFirstName = users[targetKey]["basic"].get("firstname", None)
            targetLastName = users[targetKey]["basic"].get("lastname", None)

            d5 = utils.updateDisplayNameIndex(targetKey, [myKey], targetName, None)
            d6 = utils.updateDisplayNameIndex(myKey, [targetKey], myName, None)

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
            d7 = db.batch_mutate(mutMap)


            #add to feed
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
            d8 = db.batch_insert(myItemId, "items", myItem)
            d9 = db.batch_insert(targetItemId, "items", targetItem)
            d10 = feed.pushToFeed(myKey, myItem["meta"]["uuid"], myItemId,
                                  myItemId, responseType, itemType, myKey)
            d11 = feed.pushToFeed(targetKey, targetItem["meta"]["uuid"],
                                  targetItemId, targetItemId, responseType,
                                  itemType, targetKey)

            userItemValue = ":".join([responseType, myItemId,
                                      myItemId, "activity", myKey, ""])
            d12 =  db.insert(myKey, "userItems", userItemValue,
                             myItem["meta"]['uuid'])
            userItemValue = ":".join([responseType, targetItemId, targetItemId,
                                      itemType, targetKey, ""])
            d13 =  db.insert(targetKey, "userItems", userItemValue,
                             targetItem["meta"]['uuid'])

            value = ":".join([responseType, myKey, targetItemId, itemType, targetKey])
            #notify users
            d14  = db.insert(targetKey, "notifications", targetItemId, targetItem["meta"]['uuid'])
            d15 = db.batch_insert(targetKey, "notificationItems", {targetItemId:{targetItem["meta"]['uuid']:value}})


            calls = [d1, d2, d3, d4, d5, d6, d7, d8, d9, d10, d11, d12, d13, d14, d15]
            cols = yield db.multiget_slice([myKey, targetKey] , "latestNotifications",
                                            ["incomingFriendRequests",
                                            "outGoingFriendRequests",
                                            "archivedFriendRequests"])
            cols = utils.multiSuperColumnsToDict(cols)
            for sc in cols.get(myKey, []):
                for tuuid, key in cols[myKey][sc].items():
                    if key == targetKey:
                        d = db.remove(myKey, "latestNotifications", tuuid, sc)
                        calls.append(d)
            for sc in cols.get(targetKey, []):
                for tuuid, key in cols[targetKey][sc].items():
                    if key == myKey:
                        d = db.remove(targetKey, "latestNotifications", tuuid, sc)
                        calls.append(d)

        except ttypes.NotFoundException:
            timeUUID = uuid.uuid1().bytes

            d1 = db.insert(myKey, "pendingConnections", '0', targetKey)
            d2 = db.insert(targetKey, "pendingConnections", '1', myKey)
            d3 = db.insert(targetKey, "latestNotifications", myKey, timeUUID, "incomingFriendRequests")
            d4 = db.insert(myKey, "latestNotifications", targetKey, timeUUID, "outGoingFriendRequests")

            #notify users
            calls = [d1, d2, d3, d4]
        except errors.PendingRequest:
            pass

        yield defer.DeferredList(calls)

    @defer.inlineCallbacks
    def _cancelFriendRequest(self, myKey, targetKey):


        deferreds = []

        cols = yield db.multiget_slice([myKey, targetKey], "latestNotifications",
                                        ["incomingFriendRequests",
                                        "outGoingFriendRequests",
                                        "archivedFriendRequests"])
        cols = utils.multiSuperColumnsToDict(cols)
        for sc in cols.get(myKey, []):
            for tuuid, key in cols[myKey][sc].items():
                if key == targetKey:
                    d = db.remove(myKey, "latestNotifications", tuuid, sc)
                    deferreds.append(d)
        for sc in cols.get(targetKey, []):
            for tuuid, key in cols[targetKey][sc].items():
                if key == myKey:
                    d = db.remove(targetKey, "latestNotifications", tuuid, sc)
                    deferreds.append(d)

        d1 = db.remove(myKey, "pendingConnections", targetKey)
        d2 = db.remove(targetKey, "pendingConnections", myKey)
        yield defer.DeferredList(deferreds+[d1, d2])
        #XXX: UI: remove the user from the list of pending-friend-requests


    @defer.inlineCallbacks
    def _archiveFriendRequest(self, myKey, targetKey):

        try:
            cols = yield db.get_slice(myKey, "latestNotifications", ["incomingFriendRequests"])
            cols = utils.supercolumnsToDict(cols)
            for tuuid, key in cols['incomingFriendRequests'].items():
                if key == targetKey:
                    d1 = db.remove(myKey, "latestNotifications", tuuid, "incomingFriendRequests")
                    d2 = db.insert(myKey, "latestNotifications", targetKey, tuuid, "archivedFriendRequests")
                    yield defer.DeferredList([d1, d2])
                    #XXX: UI: remove the user from pending requests list
        except ttypes.NotFoundException:
            pass



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
        mutations[myKey]["pendingConnections"] = {targetKey:None}
        mutations[myKey]["displayNameIndex"] = {_getColName(targetDisplayName, targetKey):None}
        mutations[targetKey]["connections"] = {myKey:None}
        mutations[targetKey]["pendingConnections"] = {myKey:None}
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


    @defer.inlineCallbacks
    def _changePassword(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        curr_passwd = utils.getRequestArg(request, "curr_passwd", sanitize=False)
        passwd1 = utils.getRequestArg(request, "passwd1", sanitize=False)
        passwd2 = utils.getRequestArg(request, "passwd2", sanitize=False)


        yield self._renderEditProfile(request)

        args["errorMsg"] = ""
        if not curr_passwd:
            args["errorMsg"] = "Enter current password"
        if passwd1 != passwd2:
            args["errorMsg"] = "New password didn't match"
        cols = yield db.get(myKey, "entities", "emailId", "basic")
        emailId = cols.column.value
        col = yield db.get(emailId, "userAuth", "passwordHash")
        passwdHash = col.column.value
        if curr_passwd and passwdHash != utils.md5(curr_passwd):
            args["errorMsg"] ="Incorrect Password"

        if args["errorMsg"]:
            yield renderScriptBlock(request, "profile.mako", "changePasswd",
                                    landing, "#profile-content", "set", **args)
        else:
            newPasswd = utils.md5(passwd1)
            yield db.insert(emailId, "userAuth", newPasswd, "passwordHash")
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

        for cn in ("jobTitle", "location", "desc", "name", "firstname", "lastname", "timezone"):
            val = utils.getRequestArg(request, cn)
            if val:
                userInfo.setdefault("basic", {})[cn] = val

        user = yield db.get_slice(myKey, "entities", ["basic"])
        user = utils.supercolumnsToDict(user)

        cols = yield db.get_slice(myKey, 'connections', )
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

        dp = utils.getRequestArg(request, "dp", sanitize=False)
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
        c_mobile = utils.getRequestArg(request, "c_mobile")
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
        if c_mobile:
            userInfo["contact"]["mobile"] = c_mobile

        interests = utils.getRequestArg(request, "interests")
        interests_acl = utils.getRequestArg(request, "interests_acl") or 'public'
        if interests:
            userInfo["interests"]= {}
            userInfo["interests"][interests]= interests
            userInfo["interests"]["acl"] = interests_acl

        p_email = utils.getRequestArg(request, "p_email")
        p_phone = utils.getRequestArg(request, "p_phone")
        p_mobile = utils.getRequestArg(request, "p_mobile")
        currentCity = utils.getRequestArg(request, "currentCity")
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
        if p_mobile:
            userInfo["personal"]["mobile"] = p_mobile
        if hometown:
            userInfo["personal"]["hometown"] = hometown
        if currentCity:
            userInfo["personal"]["currentCity"] = currentCity
        if dob_day and dob_mon and dob_year:
            if dob_day.isdigit() and dob_mon.isdigit() and dob_year.isdigit():
                if int(dob_day) in range(1, 31) and \
                    int(dob_mon) in range(1, 12) and \
                        int(dob_year) in range(1901, 2099):
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
            yield db.batch_insert(myKey, "entities", userInfo)
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
                raise errors.InvalidFileSize()
            if action == "edit":
                requestDeferred = self._edit(request)
            elif action == "changePasswd":
                requestDeferred = self._changePassword(request)
            return self._epilogue(request, requestDeferred)

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
                raise errors.InvalidRequest()

            relation = Relation(myKey, [targetKey])
            data = {"relations": relation}
            def fetchRelations(ign):
                return defer.DeferredList([relation.initFriendsList(),
                                           relation.initPendingList(),
                                           relation.initSubscriptionsList()])

            isProfile = (request.getCookie("page") == "profile")
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
        elif segmentCount == 1 and request.postpath[0] in ['cancel', 'archive']:
            targetKey = utils.getRequestArg(request, 'targetKey')
            authinfo = request.getSession(IAuthInfo)
            myKey = authinfo.username
            if targetKey:
                if request.postpath[0] == 'cancel':
                    d = self._cancelFriendRequest(myKey, targetKey)
                elif request.postpath[0] == 'archive':
                    d = self._archiveFriendRequest(myKey, targetKey)


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
        elif detail == "work":
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editWork",
                                    landing, "#profile-content", "set", **args)
        elif detail == "personal":
            res = yield db.get_slice(myKey, "entities", ['personal'])
            personalInfo = utils.supercolumnsToDict(res).get("personal", {})
            args.update({"personalInfo":personalInfo})
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editPersonal",
                                    landing, "#profile-content", "set", **args)
        elif detail == "contact":
            res = yield db.get_slice(myKey, "entities", ['contact'])
            contactInfo = utils.supercolumnsToDict(res).get("contact", {})
            args.update({"contactInfo":contactInfo})
            yield renderScriptBlock(request, "profile.mako", "editProfileTabs",
                                    landing, "#profile-tabs", "set", **args)
            yield renderScriptBlock(request, "profile.mako", "editContact",
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
        newId = (request.getCookie('cu') != userKey) or appchange
        if script and newId:
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

        if newId or not script:
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
