import csv
import re
from csv import reader

from telephus.cassandra import ttypes
from twisted.web        import server
from twisted.internet   import defer

from social             import base, db, utils, people, errors, tags, _
from social.isocial     import IAuthInfo
from social.signup      import getOrgKey # move getOrgKey to utils
from social.template    import render, renderScriptBlock
from social.constants   import PEOPLE_PER_PAGE
from social.settings    import saveAvatarItem
from social.logging     import log


class Admin(base.BaseResource):
    isLeaf=True

    @defer.inlineCallbacks
    def _validData(self, data, format, orgId):
        if format in ("csv", "tsv"):
            dialect = csv.excel_tab  if format == "tsv" else csv.excel
            reader = csv.reader(data.split("\n"), dialect=dialect)
            for row in reader:
                if row:
                    if len(row) < 5:
                        defer.returnValue(False)
                    email, displayName, jobTitle, passwd, timezone = row
                    domain = email.split("@")[1]
                    userOrg = yield getOrgKey(domain)
                    if userOrg != orgId:
                        defer.returnValue(False)
            defer.returnValue(True)
        else:
            defer.returnValue(False)


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

        fileUpload = True if (dataFmt or data) else False
        if fileUpload and not (dataFmt and data):
            raise errors.MissingParams([_("File")])

        if not fileUpload and not all([name, emailId, passwd, jobTitle, timezone]):
            raise errors.MissingParams([_("All fields are required to create the user")])

        if all([name, emailId, passwd, jobTitle, timezone]):
            data = ",".join([emailId, name, jobTitle, passwd, timezone])
            format = "csv"

        isValidData = yield self._validData(data, format, orgId)
        if not isValidData:
          raise errors.InvalidRequest("New user details are invalid")

        if format in ("csv", "tsv"):
            dialect = csv.excel_tab  if format == "tsv" else csv.excel
            reader = csv.reader(data.split("\n"), dialect=dialect)

            for row in reader:
                if row:
                    email, displayName, jobTitle, passwd, timezone = row
                    existingUser = yield utils.existingUser(email)
                    if existingUser:
                        log.info("%s is already a member of the network."
                                "not adding it again"%(email))
                        continue
                    userKey = yield utils.addUser(email, displayName, passwd,
                                                  orgId, jobTitle, timezone)
        request.redirect("/admin/people?type=all")


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

            args = {'affectedGroups': affectedGroups}
            args['orgAdminNewGroups'] = orgAdminNewGroups
            args['apps'] = apps
            args['userId'] = userId
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
            avatar = yield saveAvatarItem(orgId, dp, isLogo=True)
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
                                    landing, "#add-user-wrapper", "set", **args)

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
            cols = yield db.get_slice(orgId, "blockedUsers", start=start, count=toFetchCount, reverse=True)
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
        yield renderScriptBlock(request, "admin.mako", "list_tags",
                                landing, "#content", "set", **args)


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
            postpath = request.postpath
            if segmentCount == 1:
                if postpath[0] == "block":
                    dfd = self._blockUser(request)
                elif postpath[0] == "unblock":
                    dfd = self._unblockUser(request)
                elif postpath[0] == "add":
                    dfd = self._addUsers(request)
                elif postpath[0] == "delete":
                    dfd = self._deleteUser(request)
                elif postpath[0] == "org":
                    dfd = self._updateOrgInfo(request)
            elif segmentCount == 2:
                if postpath[0] == 'tags' and postpath[1] == 'add':
                    dfd = self._addPresetTag(request)
                elif postpath[0] == 'tags' and postpath[1] == 'delete':
                    dfd = self._deletePresetTag(request)
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
            elif segmentCount== 1:
                if request.postpath[0] == "add":
                    dfd = self._renderAddUsers(request)
                elif request.postpath[0] == "people":
                    dfd = self._renderUsers(request)
                elif request.postpath[0] == "org":
                    dfd = self._renderOrgInfo(request)
                elif request.postpath[0] == 'tags':
                    dfd = self._listPresetTags (request)
            if not dfd:
                raise errors.NotFoundError()
            return dfd
        d.addCallback(callback)
        return self._epilogue(request, d)
