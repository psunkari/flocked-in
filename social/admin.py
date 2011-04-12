import csv
from csv import reader

from twisted.web        import server
from twisted.internet   import defer
from twisted.python     import log
from twisted.cred.error import Unauthorized

from social             import base, Db, utils
from social.register    import getOrgKey # move getOrgKey to utils
from social.template    import render, renderScriptBlock
from social.constants   import PEOPLE_PER_PAGE

class Admin(base.BaseResource):

    isLeaf=True

    @defer.inlineCallbacks
    def _validData(self, data, format, orgKey):


        if format in ("csv", "tsv"):
            dialect = csv.excel_tab  if format == "tsv" else csv.excel
            reader = csv.reader(data.split("\n"), dialect=dialect)
            for row in reader:
                if row:
                    if len(row) < 4:
                        defer.returnValue(False)
                    email, displayName, jobTitle, passwd = row
                    domain = email.split("@")[1]
                    userOrg = yield getOrgKey(domain)
                    if userOrg != orgKey:
                        defer.returnValue(False)
            defer.returnValue(True)
        else:
            defer.returnValue(False)


    @defer.inlineCallbacks
    def _addUsers(self, request):

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]

        isAdmin = yield utils.isAdmin(myKey, orgKey)
        if not isAdmin:
            raise Unauthorized()

        format = utils.getRequestArg(request, 'format')
        data = utils.getRequestArg(request, "data")
        name = utils.getRequestArg(request, "name")
        emailId = utils.getRequestArg(request, "email")
        passwd = utils.getRequestArg(request, "passwd")
        jobTitle = utils.getRequestArg(request, "jobTitle")


        if all([format, data, name, emailId, passwd, jobTitle]):
            raise errors.TooManyParams()

        if not (format and data) and not all([name, emailId, passwd, jobTitle]):
            raise errors.MissingParams()

        if all([name, emailId, passwd, jobTitle]):
            data = ",".join([emailId, name, jobTitle, passwd])
            format = "csv"

        isValidData = yield self._validData(data, format, orgKey)
        if not isValidData:
          raise errors.InvalidData()

        if format in ("csv", "tsv"):
            dialect = csv.excel_tab  if format == "tsv" else csv.excel
            reader = csv.reader(data.split("\n"), dialect=dialect)

            for row in reader:
                if row:
                    email, displayName, jobTitle, passwd = row
                    existingUser = yield utils.existingUser(email)
                    if existingUser:
                        log.msg("%s is already a member of the network."
                                "not adding it again"%(email))
                        continue
                    userKey = yield utils.addUser(email, displayName,
                                                  passwd, orgKey, jobTitle)

    @defer.inlineCallbacks
    def _blockUser(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]
        userId = utils.getRequestArg(request, "id")

        admins = yield utils.getAdmins(orgKey)
        if myKey not in admins:
            raise Unauthorized()

        if len(admins) == 1 and userId == myKey:
            # if the network has only one admin, admin can't block himself
            raise errors.NotAllowed()

        cols = yield Db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)
        emailId = userInfo.get("basic", {}).get("emailId", None)
        userOrg = userInfo.get("basic", {}).get("org", None)

        if userOrg != orgKey:
            log.msg("can't block users of other networks")
            raise errors.UnAuthoried()
        yield Db.insert(emailId, "userAuth", 'True', "isBlocked")
        yield Db.insert(orgKey, "blockedUsers", '', userId)

    @defer.inlineCallbacks
    def _unBlockUser(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]

        isAdmin = yield utils.isAdmin(myKey, orgKey)
        if not isAdmin:
            raise Unauthorized()

        userId = utils.getRequestArg(request, "id")
        cols = yield Db.get_slice(userId, "entities", ["basic"])
        userInfo = utils.supercolumnsToDict(cols)
        emailId = userInfo.get("basic", {}).get("emailId", None)
        userOrg = userInfo.get("basic", {}).get("org", None)

        if userOrg != orgKey:
            log.msg("can't unblock users of other networks")
            raise errors.UnAuthoried()
        yield Db.remove(emailId, "userAuth", "isBlocked")
        yield Db.remove(orgKey, "blockedUsers", userId)

    @defer.inlineCallbacks
    def _renderAddUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]
        landing = not self._ajax
        isAdmin = yield utils.isAdmin(myKey, orgKey)
        if not isAdmin:
            request.write("UnAuthorized")
            raise Unauthorized()
        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "admin.mako", "addUsers",
                                    landing, "#add-users", "set", **args)

        if script and landing:
            request.write("</body></html>")

    @defer.inlineCallbacks
    def _listBlockedUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]
        landing = not self._ajax
        isAdmin = yield utils.isAdmin(myKey, orgKey)
        if not isAdmin:
            request.write("UnAuthorized")
            raise Unauthorized()

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        args["heading"] = "Admin Console - Blocked Users"
        cols = yield Db.get_slice(orgKey, "blockedUsers")
        blockedUsers = utils.columnsToDict(cols).keys()

        cols = yield Db.multiget_slice(blockedUsers, "entities", ["basic"])
        userInfo = utils.multiSuperColumnsToDict(cols)

        args["entities"] = userInfo

        if script:
            yield renderScriptBlock(request, "admin.mako", "list_blocked",
                                    landing, "#add-users", "set", **args)

        if script and landing:
            request.write("</body></html>")

    @defer.inlineCallbacks
    def _listUsers(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        orgKey = args["orgKey"]
        landing = not self._ajax
        isAdmin = yield utils.isAdmin(myKey, orgKey)
        if not isAdmin:
            raise Unauthorized()
        start = utils.getRequestArg(request, 'start') or ''

        if script and landing:
            yield render(request, "admin.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "admin.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        cols = yield Db.get_slice(orgKey, "blockedUsers")
        blockedUsers = utils.columnsToDict(cols).keys()

        cols = yield Db.get_slice(orgKey, "displayNameIndex", start=start,
                                  count=PEOPLE_PER_PAGE)
        employeeIds = [col.column.name.split(":")[1] for col in cols]
        employees = [userId for userId in employeeIds if userId not in blockedUsers]

        userInfo = yield Db.multiget_slice(employees, "entities", ["basic"])
        args["entities"] = utils.multiSuperColumnsToDict(userInfo)
        args["people"] = employees

        if script:
            yield renderScriptBlock(request, "admin.mako", "list_users",
                                    landing, "#add-users", "set", **args)

        if script and landing:
            request.write("</body></html>")


    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1 and request.postpath[0] == "block":
            d = self._blockUser(request)
        elif segmentCount == 1 and  request.postpath[0] == "unblock":
            d = self._unBlockUser(request)
        elif segmentCount == 1 and request.postpath[0] == "add":
            d = self._addUsers(request)

        return self._epilogue(request, d)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0 or (segmentCount== 1 and request.postpath[0] == "add"):
            d = self._renderAddUsers(request)
        elif segmentCount == 1 and request.postpath[0] == "unblock":
            d = self._listBlockedUsers(request)
        elif segmentCount == 1 and request.postpath[0] == "people":
            d = self._listUsers(request)

        return self._epilogue(request, d)
