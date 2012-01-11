import csv
import re
from csv import reader

from telephus.cassandra import ttypes
from twisted.web        import server
from twisted.internet   import defer
from nltk.corpus        import stopwords

from social             import base, db, utils, people, errors
from social             import tags, plugins, location_tz_map, _
from social.item        import deleteItem
from social.isocial     import IAuthInfo
from social.signup      import getOrgKey # move getOrgKey to utils
from social.template    import render, renderScriptBlock
from social.constants   import PEOPLE_PER_PAGE
from social.settings    import saveAvatarItem
from social.logging     import log


class Admin(base.BaseResource):
    isLeaf=True

    @defer.inlineCallbacks
    def _validData(self, data, orgId):
        timezones = location_tz_map.values()
        for row in data:
            if row:
                if len(row) !=5:
                    defer.returnValue(False)
                displayName, email, jobTitle, timezone, passwd = row
                if timezone not in timezones:
                    defer.returnValue(False)
                try:
                    domain = email.split("@")[1]
                except IndexError:
                    defer.returnValue(False)
                #XXX: validate all the domains at once.
                userOrg = yield getOrgKey(domain)
                if userOrg != orgId:
                    defer.returnValue(False)
        defer.returnValue(True)


    @defer.inlineCallbacks
    def _addUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]

        # File upload
        dataFmt = utils.getRequestArg(request, 'format')
        data = utils.getRequestArg(request, "data", sanitize=False)

        # Form submit - single user addtion
        name = utils.getRequestArg(request, "name")
        emailId = utils.getRequestArg(request, "email", sanitize=False)
        passwd = utils.getRequestArg(request, "passwd", sanitize=False)
        jobTitle = utils.getRequestArg(request, "jobTitle")
        timezone = utils.getRequestArg(request, "timezone")
        existingUsers = set()

        fileUpload = True if (dataFmt or data) else False

        if fileUpload and not (dataFmt and data):
            raise errors.MissingParams([_("File")])

        if fileUpload and dataFmt not in ('csv', 'tsv'):
            raise errors.InvalidRequest("New user details are invalid")

        if not fileUpload and not all([name, emailId, passwd, jobTitle, timezone]):
            raise errors.MissingParams([_("All fields are required to create the user")])

        if dataFmt in ("csv", "tsv"):
            dialect = csv.excel_tab  if dataFmt == "tsv" else csv.excel
            data = csv.reader(data.split("\n"), dialect=dialect)
            data = [row for row in data]
        if all([name, emailId, passwd, jobTitle, timezone]):
            data = [[name, emailId, jobTitle, timezone, passwd]]


        isValidData = yield self._validData(data, orgId)
        if not isValidData:
          if fileUpload:
            request.write("<script>parent.$$.alerts.error('Invalid file');")
          raise errors.InvalidRequest("New user details are invalid")

        for row in data:
            if row:
                displayName, email, jobTitle, timezone, passwd = row
                existingUser = yield utils.existingUser(email)
                if existingUser:
                    log.info("%s is already a member of the network."
                            "not adding it again"%(email))
                    existingUsers.add(email)
                    continue
                userKey = yield utils.addUser(email, displayName, passwd,
                                              orgId, jobTitle, timezone)
        if not fileUpload:
            if existingUsers:
                response = """
                                $$.alerts.error('User is already in the network.');
                                $$.dialog.close('addpeople-dlg', true);

                            """
            else:
                response = """
                                $$.alerts.info('User Added');
                                $$.dialog.close('addpeople-dlg', true);
                                $$.fetchUri('/admin/people?type=all');

                            """
        else:
            response = """
                            <script>
                            parent.$$.alerts.info('Users Added');
                            parent.$$.fetchUri('/admin/people?type=all');
                            parent.$$.dialog.close('addpeople-dlg', true);
                            </script>

                        """

        request.write(response)


    @defer.inlineCallbacks
    def _blockUser(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        userId, user = yield utils.getValidEntityId(request, "id")

        # Admin cannot block himself.
        if userId == myId:
            raise errors.InvalidRequest(_("You cannot block yourself."))

        emailId = user.get("basic", {}).get("emailId", None)
        yield db.insert(emailId, "userAuth", 'True', "isBlocked")
        yield db.insert(orgId, "blockedUsers", '', userId)
        yield renderScriptBlock(request, "admin.mako", "admin_actions",
                                False, "#user-actions-%s" %(userId),
                                "set", args=[userId, 'blocked'])


    @defer.inlineCallbacks
    def _unblockUser(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        userId, user = yield utils.getValidEntityId(request, "id")
        emailId = user.get("basic", {}).get("emailId", None)

        yield db.remove(emailId, "userAuth", "isBlocked")
        yield db.remove(orgId, "blockedUsers", userId)
        yield renderScriptBlock(request, "admin.mako", "admin_actions",
                                False, "#user-actions-%s" %(userId),
                                "set", args=[userId, 'unblocked'])


    @defer.inlineCallbacks
    def _deleteUser(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        userId, user = yield utils.getValidEntityId(request, "id")
        delete = utils.getRequestArg(request, 'deleted') == 'deleted'

        # Admin cannot block himself.
        if userId == myId:
            raise errors.InvalidRequest(_("You are the only administrator, you can not delete yourself"))

        if delete:
            yield utils.removeUser(request, userId, myId, user)
            yield renderScriptBlock(request, "admin.mako", "admin_actions",
                                    False, "#user-actions-%s" %(userId),
                                    "set", args=[userId, 'deleted'])
        else:
            orgAdminNewGroups = []
            affectedGroups = []
            groups = yield db.get_slice(userId, "entityGroupsMap")
            groupIds = [x.column.name.split(':')[1] for x in groups]
            groupAdmins = yield db.multiget_slice(groupIds, "entities", ['admins'])
            groupAdmins = utils.multiSuperColumnsToDict(groupAdmins)
            for group in groups:
                name, groupId = group.column.name.split(':')
                if len(groupAdmins[groupId].get('admins', {}))==1 and userId in groupAdmins[groupId]['admins']:
                    orgAdminNewGroups.append((groupId, name))
                affectedGroups.append((groupId, name))

            apiKeys = yield db.get_slice(userId, "entities", ['apikeys'])
            apiKeys = utils.supercolumnsToDict(apiKeys)
            if apiKeys.get('apikeys', {}).keys():
                apps = yield db.multiget_slice(apiKeys['apikeys'].keys(), "apps", ['meta'])
                apps = utils.multiSuperColumnsToDict(apps)
            else :
                apps = {}

            cols = yield db.multiget_slice([userId], "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(cols)

            args = {'affectedGroups': affectedGroups}
            args['orgAdminNewGroups'] = orgAdminNewGroups
            args['apps'] = apps
            args['userId'] = userId
            args["entities"] = entities
            yield renderScriptBlock(request, 'admin.mako', "confirm_remove_user",
                                    False, "#removeuser-dlg", "set", **args)


    @defer.inlineCallbacks
    def _updateOrgInfo(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]

        name = utils.getRequestArg(request, "name")
        dp = utils.getRequestArg(request, "dp", sanitize=False)

        orgInfo = {}
        if dp:
            avatar = yield saveAvatarItem(orgId, orgId, dp, isLogo=True)
            if not orgInfo.has_key("basic"):
                orgInfo["basic"] = {}
            orgInfo["basic"]["logo"] = avatar
        if name:
            if "basic" not in orgInfo:
                orgInfo["basic"] = {}
            orgInfo["basic"]["name"] = name
            args['org']['basic']['name'] = name
        if orgInfo:
            yield db.batch_insert(orgId, "entities", orgInfo)

        ###TODO: update orgImage when image is uploaded.
        request.write("""<script>
                            parent.$$.alerts.info('update successful');
                        </script>""")


    @defer.inlineCallbacks
    def _renderOrgInfo(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        args['title'] = "Update Company Info"
        args["menuId"] = "org"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        orgInfo = yield db.get_slice(orgId, "entities", ['basic'])
        orgInfo = utils.supercolumnsToDict(orgInfo)

        args["orgInfo"]= orgInfo
        args["viewType"] = "org"

        if script:
            handlers = {'onload': "$$.ui.bindFormSubmit('#orginfo-form');"}
            yield renderScriptBlock(request, "admin.mako", "orgInfo",
                                    landing, "#content", "set", True,
                                    handlers = handlers, **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "admin.mako", **args)

    @defer.inlineCallbacks
    def _renderAddUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        args["title"] = "Add Users"
        args["viewType"] = "add"
        args["menuId"] = "users"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "admin.mako", "addUsers",
                                    landing, "#addpeople-dlg", "set", **args)

        if script and landing:
            request.write("</body></html>")


    @defer.inlineCallbacks
    def _listBlockedUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax
        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        count = PEOPLE_PER_PAGE
        toFetchCount = count+1
        nextPageStart = ''
        prevPageStart = ''
        args["title"] = "Manage Users"
        args["menuId"] = "users"
        args["viewType"] = "blocked"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        args["heading"] = "Admin Console - Blocked Users"
        cols = yield db.get_slice(orgId, "blockedUsers", start=start, count=toFetchCount)
        blockedUsers = [col.column.name for col in cols]
        if len(blockedUsers) > count:
            nextPageStart = utils.encodeKey(blockedUsers[-1])
            blockedUsers = blockedUsers[:count]
        if start:
            cols = yield db.get_slice(orgId, "blockedUsers", start=start,
                                      count=toFetchCount, reverse=True)
            if len(cols) > 1:
                prevPageStart = utils.decodeKey(cols[-1].column.name)

        cols = yield db.multiget_slice(blockedUsers, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(cols)

        args["entities"] = entities
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            yield renderScriptBlock(request, "admin.mako", "viewOptions",
                                landing, "#users-view", "set", **args)
            yield renderScriptBlock(request, "admin.mako", "list_users",
                                    landing, "#content", "set", **args)

        if script and landing:
            request.write("</body></html>")
        if not script:
            yield render(request, "admin.mako", **args)



    @defer.inlineCallbacks
    def _listAllUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        start = utils.getRequestArg(request, 'start') or ''
        args["title"] = "Manage Users"
        args["menuId"] = "users"
        args["viewType"] = "all"
        start = utils.decodeKey(start)

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        users, relations, userIds,blockedUsers,\
            nextPageStart, prevPageStart = yield people.getPeople(myKey, orgId, orgId, start=start)

        args["entities"] = users
        args["relations"] = relations
        args["people"] = userIds
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["blockedUsers"] = blockedUsers

        if script:
            yield renderScriptBlock(request, "admin.mako", "viewOptions",
                                landing, "#users-view", "set", **args)

            yield renderScriptBlock(request, "admin.mako", "list_users",
                                    landing, "#content", "set", **args)
        else:
            yield render(request, "admin.mako", **args)



    @defer.inlineCallbacks
    def _renderUsers(self, request):
        type = utils.getRequestArg(request, 'type') or 'all'
        if type == "all":
            yield self._listAllUsers(request)
        else:
            yield self._listBlockedUsers(request)


    @defer.inlineCallbacks
    def _ignoreKeywordMatched(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        keyword = utils.getRequestArg(request, "keyword")
        (itemId, item) = yield utils.getValidItemId(request, 'id')

        # Remove this item from this list of keywordItems.
        timeUUID = item["meta"]["uuid"]
        yield db.remove(myOrgId+":"+keyword, "keywordItems", timeUUID)

        # Update the UI
        request.write("$$.convs.remove('%s');"%itemId)


    @defer.inlineCallbacks
    def _removeKeywordMatched(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        (itemId, item) = yield utils.getValidItemId(request, 'id')
        yield deleteItem(request, itemId)

        # Update the UI
        request.write("$$.convs.remove('%s');"%itemId)


    @defer.inlineCallbacks
    def _getKeywordMatches(self, request, keyword, start='', count=10):
        args = {}
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        items = {}
        itemIds = []
        itemIdKeyMap = {}
        allFetchedItems = set()
        deleted = set()

        fetchStart = utils.decodeKey(start)
        fetchCount = count + 2
        while len(itemIds) < count:
            fetchedItemIds = []
            toFetchItems = set()

            results = yield db.get_slice(myOrgId+":"+keyword, "keywordItems",
                                         count=fetchCount, start=fetchStart,
                                         reverse=True)
            for col in results:
                fetchStart = col.column.name
                itemAndParentIds = col.column.value.split(':')
                itemIdKeyMap[itemAndParentIds[0]] = fetchStart
                fetchedItemIds.append(itemAndParentIds[0])
                for itemId in itemAndParentIds:
                    if itemId not in allFetchedItems:
                        toFetchItems.add(itemId)
                        allFetchedItems.add(itemId)

            if toFetchItems:
                fetchedItems = yield db.multiget_slice(toFetchItems, "items",
                                                       ["meta", "attachments"])
                fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
                items.update(fetchedItems)

            for itemId in fetchedItemIds:
                item = items[itemId]
                if not 'meta' in item:
                    continue

                state = item['meta'].get('state', 'published')
                if state == 'deleted':
                    deleted.add(itemIdKeyMap[itemId])
                elif utils.checkAcl(myId, myOrgId, True, None, item['meta']):
                    itemIds.append(itemId)

            if len(results) < fetchCount:
                break

        if len(itemIds) > count:
            nextPageStart = utils.encodeKey(itemIdKeyMap[itemIds[-1]])
            itemIds = itemIds[:-1]
        else:
            nextPageStart = None

        dd = db.batch_remove({'keywordItems': [myOrgId+':'+keyword]},
                             names=deleted) if deleted else defer.succeed([])

        args.update({'items': items, 'myKey': myId})
        toFetchEntities = set()
        extraDataDeferreds = []
        for itemId in itemIds:
            item = items[itemId]
            toFetchEntities.add(item['meta']['owner'])
            if 'target' in item['meta']:
                toFetchEntities.update(item['meta']['target'].split(','))
            itemType = item['meta'].get('type', 'status')
            if itemType in plugins:
                d = plugins[itemType].fetchData(args, itemId)
                extraDataDeferreds.append(d)

        result = yield defer.DeferredList(extraDataDeferreds)
        for success, ret in result:
            if success:
                toFetchEntities.update(ret)

        fetchedEntities = {}
        if toFetchEntities:
            fetchedEntities = yield db.multiget_slice(toFetchEntities,
                                                      "entities", ["basic"])
            fetchedEntities = utils.multiSuperColumnsToDict(fetchedEntities)

        yield dd
        args.update({'entities': fetchedEntities,
                     'matches': itemIds, 'nextPageStart': nextPageStart})
        defer.returnValue(args)


    @defer.inlineCallbacks
    def _renderKeywordMatches(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        keyword = utils.getRequestArg(request, 'keyword')
        if not keyword:
            errors.MissingParams(['Keyword'])
        args["keyword"] = keyword

        start = utils.getRequestArg(request, "start") or ""
        args["start"] = start

        if script and landing:
            yield render(request, "keyword-matches.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "keyword-matches.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        keywordItems = yield self._getKeywordMatches(request, keyword, start=start)
        args.update(keywordItems)

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            yield renderScriptBlock(request, "keyword-matches.mako", "feed",
                                    landing, "#convs-wrapper", "set", True,
                                    handlers={"onload": onload}, **args)

        if not script:
            yield render(request, "keyword-matches.mako", **args)


    @defer.inlineCallbacks
    def _renderKeywordMatchesMore(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        keyword = utils.getRequestArg(request, 'keyword')
        if not keyword:
            errors.MissingParams(['Keyword'])
        args["keyword"] = keyword

        start = utils.getRequestArg(request, "start") or ""
        args["start"] = start

        keywordItems = yield self._getKeywordMatches(request, keyword, start=start)
        args.update(keywordItems)

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        yield renderScriptBlock(request, "keyword-matches.mako", "feed",
                                False, "#next-load-wrapper", "replace", True,
                                handlers={"onload": onload}, **args)


    @defer.inlineCallbacks
    def _renderKeywordManagement(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        args["title"] = "Keyword Monitoring"
        args["menuId"] = "keywords"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        keywords = yield db.get_slice(orgId, "originalKeywords")
        keywords = utils.columnsToDict(keywords, ordered=True)
        args['keywords'] = keywords

        if script:
            yield renderScriptBlock(request, "admin.mako", "listKeywords",
                                landing, "#content", "set", **args)


    @defer.inlineCallbacks
    def _addKeywords(self, request):
        orgId = request.getSession(IAuthInfo).organization
        keywords = utils.getRequestArg(request, 'keywords', sanitize=False) or ''
        exactMatch = utils.getRequestArg(request, 'exactMatch')
        exactMatch = True
        keywords = [x.strip() for x in keywords.split(',')]

        # remove stopwords
        keywords = set([x.decode('utf-8', 'replace').lower().encode('utf-8') \
                       for x in keywords if x not in stopwords.words()])
        for keyword in keywords:
            yield db.insert(orgId, "keywords", '', keyword)
            yield db.insert(orgId, "originalKeywords", '', keyword)

        keywords = yield db.get_slice(orgId, "originalKeywords", count=100)
        keywords = utils.columnsToDict(keywords, ordered=True)
        args = {'keywords': keywords}

        yield renderScriptBlock(request, "admin.mako", "listKeywords",
                                False, "#content", "set", **args)


    @defer.inlineCallbacks
    def _deleteKeyword(self, request):
        orgId = request.getSession(IAuthInfo).organization
        keyword = utils.getRequestArg(request, 'keyword') or ''
        keyword = utils.decodeKey(keyword)

        if not keyword:
            return

        yield db.remove(orgId, "keywords", keyword)
        yield db.remove(orgId, "originalKeywords", keyword)
        yield db.remove(orgId+':'+keyword, "keywordItems")

        request.write('$("#keyword-%s").remove()'%(utils.encodeKey(keyword)))


    @defer.inlineCallbacks
    def _ensureAdmin(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if not authinfo.isAdmin:
            raise errors.PermissionDenied(_("Only company administrators are allowed here!"))


    @defer.inlineCallbacks
    def _listPresetTags(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        args['title'] = 'Preset Tags'
        args['menuId'] = 'tags'
        args["viewType"] = "tags"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        presetTags = yield db.get_slice(orgId, "orgPresetTags", count=100)
        presetTags = utils.columnsToDict(presetTags, ordered=True).values()
        if presetTags:
          tags = yield db.get_slice(orgId, "orgTags", presetTags)
          tags = utils.supercolumnsToDict(tags)
        else:
          tags = {}

        args['tagsList'] = presetTags
        args['tags'] = tags
        if script:
            yield renderScriptBlock(request, "admin.mako", "list_tags",
                                    landing, "#content", "set", **args)

        if not script:
            yield render(request, "admin.mako", **args)

    @defer.inlineCallbacks
    def _addPresetTag(self, request):
        orgId = request.getSession(IAuthInfo).organization
        tagNames = utils.getRequestArg(request, 'tag')
        if not tagNames:
            return

        invalidTags = []
        tagNames = [x.strip().decode('utf-8', 'replace') for x in tagNames.split(',')]
        for tagName in tagNames:
            if len(tagName) < 50 and re.match('^[\w-]*$', tagName):
                yield tags.ensureTag(request, tagName, orgId, True)
            else:
                invalidTags.append(tagName)

        presetTags = yield db.get_slice(orgId, "orgPresetTags")
        presetTags = utils.columnsToDict(presetTags, ordered=True).values()

        tags_ = yield db.get_slice(orgId, "orgTags", presetTags)
        tags_ = utils.supercolumnsToDict(tags_)
        args = {'tags': tags_, 'tagsList': presetTags}

        handlers = {}
        if invalidTags:
            if len(invalidTags) == 1:
                message = " %s is invalid tag. " %(invalidTags[0])
            else:
                message = " %s are invalid tags. " %(",".join(invalidTags))
            errorMsg =  "%s <br/>Tag can contain alpha-numeric characters or hyphen only. It cannot be more than 50 characters" %(message)
            handlers = {'onload': "$$.alerts.error('%s')"%(errorMsg)}

        yield renderScriptBlock(request, "admin.mako", "list_tags",
                                False, "#content", "set", True,
                                handlers = handlers,  **args)


    @defer.inlineCallbacks
    def _deletePresetTag(self, request):
        orgId = request.getSession(IAuthInfo).organization
        tagId = utils.getRequestArg(request, 'id')
        if not tagId:
            return

        try:
            tag = yield db.get(orgId, 'orgTags', super_column = tagId)
            tag = utils.supercolumnsToDict([tag])
            tagName = tag[tagId]['title']
            if 'isPreset' in tag[tagId]:
                yield db.remove(orgId, "orgTags", 'isPreset', tagId)
                yield db.remove(orgId, 'orgPresetTags', tagName)
            presetTags = yield db.get_slice(orgId, "orgPresetTags")
            presetTags = utils.columnsToDict(presetTags, ordered=True).values()
            if presetTags:
              tags = yield db.get_slice(orgId, "orgTags", presetTags)
              tags = utils.supercolumnsToDict(tags)
            else:
              tags = {}
            args = {'tagsList': presetTags, 'tags': tags}
            request.write('$("#tag-%s").remove()'%(tagId))
        except ttypes.NotFoundException:
            return


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = self._ensureAdmin(request)
        def callback(ignored):
            dfd = None
            if segmentCount == 1:
                action = request.postpath[0]
                if action == "block":
                    dfd = self._blockUser(request)
                elif action == "unblock":
                    dfd = self._unblockUser(request)
                elif action == "add":
                    dfd = self._addUsers(request)
                elif action == "delete":
                    dfd = self._deleteUser(request)
                elif action == "org":
                    dfd = self._updateOrgInfo(request)
            elif segmentCount == 2:
                section = request.postpath[0]
                action = request.postpath[1]
                if section == 'tags':
                    if action == 'add':
                        dfd = self._addPresetTag(request)
                    elif action == 'delete':
                        dfd = self._deletePresetTag(request)
                elif section == 'keywords':
                    if action=='add':
                        dfd = self._addKeywords(request)
                    elif action=='delete':
                        dfd = self._deleteKeyword(request)
                    elif action == "ignore":
                        dfd = self._ignoreKeywordMatched(request)
                    elif action == "hide":
                        dfd = self._removeKeywordMatched(request)
            if not dfd:
                raise errors.NotFoundError()
            return dfd

        d.addCallback(callback)
        return self._epilogue(request, d)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = self._ensureAdmin(request)
        def callback(ignored):
            dfd = None
            if segmentCount == 0:
                dfd = self._renderUsers(request)
            elif segmentCount == 1:
                action = request.postpath[0]
                if action == "add":
                    dfd = self._renderAddUsers(request)
                elif action == "people":
                    dfd = self._renderUsers(request)
                elif action == "org":
                    dfd = self._renderOrgInfo(request)
                elif action == 'tags':
                    dfd = self._listPresetTags (request)
                elif action == 'keywords':
                    dfd = self._renderKeywordManagement(request)
                elif action == 'keyword-matches':
                    dfd = self._renderKeywordMatches(request)
                elif action == 'keyword-matches-more':
                    dfd = self._renderKeywordMatchesMore(request)
            if not dfd:
                raise errors.NotFoundError()
            return dfd

        d.addCallback(callback)
        return self._epilogue(request, d)

