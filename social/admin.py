import csv
from csv import reader

from twisted.web        import server
from twisted.internet   import defer
from twisted.python     import log

from social             import base, db, utils, people
from social.signup      import getOrgKey # move getOrgKey to utils
from social.template    import render, renderScriptBlock
from social.constants   import PEOPLE_PER_PAGE
from social.profile     import saveAvatarItem

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

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()

        format = utils.getRequestArg(request, 'format')
        data = utils.getRequestArg(request, "data", sanitize=False)
        name = utils.getRequestArg(request, "name")
        emailId = utils.getRequestArg(request, "email", sanitize=False)
        passwd = utils.getRequestArg(request, "passwd", sanitize=False)
        jobTitle = utils.getRequestArg(request, "jobTitle")
        timezone = utils.getRequestArg(request, "timezone")
        log.msg(name, emailId, passwd, jobTitle, timezone)


        if all([format, data, name, emailId, passwd, jobTitle]):
            raise errors.TooManyParams()

        if not (format and data) and not all([name, emailId, passwd, jobTitle, timezone]):
            raise errors.MissingParams()

        if all([name, emailId, passwd, jobTitle, timezone]):
            data = ",".join([emailId, name, jobTitle, passwd, timezone])
            format = "csv"

        isValidData = yield self._validData(data, format, orgId)
        if not isValidData:
          raise errors.InvalidData()

        if format in ("csv", "tsv"):
            dialect = csv.excel_tab  if format == "tsv" else csv.excel
            reader = csv.reader(data.split("\n"), dialect=dialect)

            for row in reader:
                if row:
                    email, displayName, jobTitle, passwd, timezone = row
                    existingUser = yield utils.existingUser(email)
                    if existingUser:
                        log.msg("%s is already a member of the network."
                                "not adding it again"%(email))
                        continue
                    userKey = yield utils.addUser(email, displayName, passwd,
                                                  orgId, jobTitle, timezone)
        request.redirect("/admin/people?type=all")

    @defer.inlineCallbacks
    def _blockUser(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        userId = utils.getRequestArg(request, "id")

        admins = yield utils.getAdmins(orgId)
        if myKey not in admins:
            raise errors.Unauthorized()

        if len(admins) == 1 and userId == myKey:
            # if the network has only one admin, admin can't block himself
            raise errors.InvalidRequest()

        cols = yield db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)
        emailId = userInfo.get("basic", {}).get("emailId", None)
        userOrg = userInfo.get("basic", {}).get("org", None)

        if userOrg != orgId:
            log.msg("can't block users of other networks")
            raise errors.Unauthorized()
        yield db.insert(emailId, "userAuth", 'True', "isBlocked")
        yield db.insert(orgId, "blockedUsers", '', userId)

    @defer.inlineCallbacks
    def _unBlockUser(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()

        userId = utils.getRequestArg(request, "id")
        cols = yield db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)
        emailId = userInfo.get("basic", {}).get("emailId", None)
        userOrg = userInfo.get("basic", {}).get("org", None)

        if userOrg != orgId:
            log.msg("can't unblock users of other networks")
            raise errors.Unauthorized()
        yield db.remove(emailId, "userAuth", "isBlocked")
        yield db.remove(orgId, "blockedUsers", userId)

    @defer.inlineCallbacks
    def _deleteUser(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()

        userId = utils.getRequestArg(request, "id")
        userId, user = utils.getValidEntityId(request, "id", "user")
        userOrg = user.get("basic", {}).get("org", None)

        if userOrg != orgId:
            log.msg("can't unblock users of other networks")
            raise errors.Unauthorzied()

        yield utils.removeUser(userId, userInfo)

    @defer.inlineCallbacks
    def _updateOrgInfo(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()
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
        if orgInfo:
            yield db.batch_insert(orgId, "entities", orgInfo)
        request.redirect('/admin/org')

    @defer.inlineCallbacks
    def _renderOrgInfo(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()
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
            yield renderScriptBlock(request, "admin.mako", "orgInfo",
                                    landing, "#list-users", "set", **args)

        if script and landing:
            request.write("</body></html>")


    @defer.inlineCallbacks
    def _renderAddUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if not args["isOrgAdmin"]:
            request.write("Unauthorized")
            raise errors.Unauthorized()
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

        if not args["isOrgAdmin"]:
            request.write("Unauthorized")
            raise errors.Unauthorized()

        args["menuId"] = "users"

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        args["heading"] = "Admin Console - Blocked Users"
        cols = yield db.get_slice(orgId, "blockedUsers")
        blockedUsers = utils.columnsToDict(cols).keys()

        cols = yield db.multiget_slice(blockedUsers, "entities", ["basic"])
        userInfo = utils.multiSuperColumnsToDict(cols)

        args["entities"] = userInfo
        args["viewType"] = "blocked"

        if script:
            yield renderScriptBlock(request, "admin.mako", "viewOptions",
                                landing, "#users-view", "set", **args)

            yield renderScriptBlock(request, "admin.mako", "list_blocked",
                                    landing, "#list-users", "set", **args)

        if script and landing:
            request.write("</body></html>")

    @defer.inlineCallbacks
    def _listUnBlockedUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgId = args["orgKey"]
        landing = not self._ajax

        if not args["isOrgAdmin"]:
            raise errors.Unauthorized()

        start = utils.getRequestArg(request, 'start') or ''
        args["title"] = "Manage Users"
        args["menuId"] = "users"

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
        args["viewType"] = "all"


        if script:
            yield renderScriptBlock(request, "admin.mako", "viewOptions",
                                landing, "#users-view", "set", **args)

            yield renderScriptBlock(request, "admin.mako", "list_users",
                                    landing, "#list-users", "set", **args)

    @defer.inlineCallbacks
    def _renderUsers(self, request):
        type = utils.getRequestArg(request, 'type') or 'all'
        if type == "all":
            yield self._listUnBlockedUsers(request)
        else:
            yield self._listBlockedUsers(request)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1 and request.postpath[0] == "block":
            d = self._blockUser(request)
        elif segmentCount == 1 and  request.postpath[0] == "unblock":
            d = self._unBlockUser(request)
        elif segmentCount == 1 and request.postpath[0] == "add":
            d = self._addUsers(request)
        elif segmentCount == 1 and request.postpath[0] == "delete":
            d = self._deleteUser(request)
        elif segmentCount == 1 and request.postpath[0] == "org":
            d = self._updateOrgInfo(request)

        return self._epilogue(request, d)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._renderUsers(request)
        elif segmentCount== 1 and request.postpath[0] == "add":
            d = self._renderAddUsers(request)
        elif segmentCount == 1 and request.postpath[0] == "people":
            d = self._renderUsers(request)
        elif segmentCount == 1 and request.postpath[0] == "org":
            d = self._renderOrgInfo(request)

        return self._epilogue(request, d)
