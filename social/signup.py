import PythonMagick
import imghdr
from hashlib            import md5

from twisted.python     import log
from twisted.internet   import defer
from twisted.web        import server, resource, static
from twisted.mail.smtp  import sendmail
from twisted.cred.error import Unauthorized
from telephus.cassandra import ttypes
from email.mime.text    import MIMEText

import social.constants as constants
from social.base        import BaseResource
from social             import utils, Db, Config
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


class SignupResource(BaseResource):
    isLeaf = True
    requireAuth = False
    thanksPage = None

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
            args = {}
            args['emailId'] = emailId
            args['view'] = 'userinfo'
            yield render(request, "signup.mako", **args)
        except ttypes.NotFoundException, e:
            raise errors.InvalidActivationToken()
        except Exception, e:
            log.msg(e)


    @defer.inlineCallbacks
    def _invite(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if not authinfo.username:
            raise errors.NotAuthorized()

        rawEmailIds = utils.getRequestArg(request, 'email', True) or []
        d = people.invite(request, rawEmailIds)
        request.redirect('/feed')


    # We are currently in a private demo mode.
    # Signups => Notify when we are public :)
    # We categorize them by domains, so that we can rollout by domain.
    @defer.inlineCallbacks
    def _signup(self, request):
        if not self.thanksPage:
            self.thanksPage = static.File("private/thanks.html")

        emailId = utils.getRequestArg(request, "email")
        local, domain = emailId.split('@')
        yield Db.insert(domain, "notifyOnRelease", '', emailId)
        self.thanksPage.render_GET(request)


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

        # We use a static.File resource to render thanks page.
        # It will take care of calling request.finish asyncly
        if segmentCount == 1 and request.postpath[0] == "signup":
            d = self._signup(request)
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            d.addErrback(errback)
            return server.NOT_DONE_YET
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == 'invite' :
                d = self._invite(request)
            elif action == 'create':
                d = self._addUser(request)
            return self._epilogue(request, d)
        else:
            return self._epilogue(request)
