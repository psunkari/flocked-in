import PythonMagick
import imghdr
from hashlib            import md5

from twisted.python     import log
from twisted.internet   import defer
from twisted.web        import server, resource
from twisted.mail.smtp  import sendmail
from twisted.cred.error import Unauthorized
from telephus.cassandra import ttypes
from email.mime.text    import MIMEText

import social.constants as constants
from social.base        import BaseResource
from social             import utils, Db, Config, whitelist, blacklist
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import dump_args, profile


@profile
@defer.inlineCallbacks
@dump_args
def getOrgKey(domain):
    cols = yield Db.get_slice(domain, "domainOrgMap")
    cols = utils.columnsToDict(cols)
    orgKey = cols.keys()[0] if cols else None
    defer.returnValue(orgKey)


class RegisterResource(BaseResource):
    isLeaf = True
    requireAuth = False

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _isValidMailId(self, inviteeDomain, sender):
        col = yield Db.get(sender, "userAuth", 'org')
        orgKey = col.column.value
        cols = yield Db.get_slice(orgKey, "entities", super_column="domains")
        cols = utils.columnsToDict(cols)
        domains = cols.keys()

        defer.returnValue(inviteeDomain and inviteeDomain in domains)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _isValidToken(self, request):
        emailId = utils.getRequestArg(request, "emailId")
        token = utils.getRequestArg(request, "token")

        try:
            userKey = yield Db.get(emailId, "userAuth", "user")
            request.redirect("/signin")
            request.finish()
            return
        except:
            pass

        try:
            local, domain = emailId.split('@')
            token = yield Db.get(domain, "invitations", token, emailId)
            args = request.args
            args['emailId'] = emailId
            args['view'] = 'userinfo'
            yield render(request, "signup.mako", **args)
            request.finish()
        except ttypes.NotFoundException, e:
            raise errors.InvalidActivationToken()
        except Exception, e:
            log.msg(e)


    @defer.inlineCallbacks
    def _invite(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if not authinfo.username:
            raise errors.NotAuthorized()

        rawEmailIds = request.args.get('email')
        d = people.invite(request, rawEmailIds)
        request.redirect('/feed')


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addUser(self, request):
        @defer.inlineCallbacks
        def setCookie(userId, orgId=None):
            authinfo = yield request.getSession(IAuthInfo)
            authinfo.username = userId
            authinfo.organization = orgId
            authinfo.isAdmin = False

        landing = not self._ajax
        emailId = utils.getRequestArg(request, 'emailId')
        domain = emailId.split("@")[1]
        passwd = utils.getRequestArg(request, 'password')
        pwdrepeat = utils.getRequestArg(request, 'pwdrepeat')
        username = utils.getRequestArg(request, 'name')
        title = utils.getRequestArg(request, 'jobTitle')
        timezone = utils.getRequestArg(request, 'timezone')
        args= {'emailId': emailId, 'view':'invite'}

        if passwd != pwdrepeat:
            raise errors.PasswordsNoMatch()

        username = username if username else emailId
        existingUser = yield Db.get_count(emailId, "userAuth")
        if not existingUser:
            orgKey = yield getOrgKey(domain)
            if not orgKey:
                orgKey = utils.getUniqueKey()
                domains = {domain:''}
                basic = {"name":domain, "type":"org"}
                yield Db.batch_insert(orgKey, "entities", {"basic": basic, "domains":domains})
                yield Db.insert(domain, "domainOrgMap", '', orgKey)

            userKey = yield utils.addUser(emailId, username, passwd,
                                          orgKey, title, timezone)
            yield Db.remove(domain, "invitations", super_column=emailId)
            setCookie(userKey, orgKey)
            yield render(request, "signup.mako", **args)

        else:
            request.redirect('/signin')
            raise errors.ExistingUser()


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._isValidToken(request)

        return self._epilogue(request, d)



    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        if segmentCount == 1 and request.postpath[0] == 'invite' :
            d = self._invite(request)
        elif segmentCount == 1 and request.postpath[0] == 'create':
            d = self._addUser(request)
        else:
            return resource.NoResource("Page not Found")

        return self._epilogue(request, d)
