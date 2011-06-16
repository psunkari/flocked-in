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
from social             import utils, db, config, people
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import dump_args, profile


@profile
@defer.inlineCallbacks
@dump_args
def getOrgKey(domain):
    cols = yield db.get_slice(domain, "domainOrgMap")
    cols = utils.columnsToDict(cols)
    orgKey = cols.keys()[0] if cols else None
    defer.returnValue(orgKey)


class SignupResource(BaseResource):
    isLeaf = True
    requireAuth = False
    thanksPage = None

    @defer.inlineCallbacks
    def _isValidToken(self, emailId, token):
        if not emailId or not token:
            defer.returnValue(False)

        try:
            yield db.get(emailId, "userAuth", "user")
            defer.returnValue(False)
        except: pass
        try:
            local, domain = emailId.split('@')
            yield db.get(domain, "invitations", token, emailId)
        except ttypes.NotFoundException, e:
            defer.returnValue(False)

        defer.returnValue(True)

    # Link that is sent in mails.
    @defer.inlineCallbacks
    def _signupCheckToken(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username:
            raise errors.AlreadySignedIn()

        emailId = utils.getRequestArg(request, "email")
        token = utils.getRequestArg(request, "token")

        valid = yield self._isValidToken(emailId, token)
        if not valid:
            raise errors.InvalidRegistration()

        args = {'emailId': emailId, 'token': token, 'view': 'userinfo'}
        yield render(request, "signup.mako", **args)

    # Results of first step in signup - basic user information
    @defer.inlineCallbacks
    def _signupGotUserData(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username:
            raise errors.AlreadySignedIn()

        emailId = utils.getRequestArg(request, "email")
        token = utils.getRequestArg(request, "token")

        valid = yield self._isValidToken(emailId, token)
        if not valid:
            raise errors.InvalidRegistration()

        yield self._addUser(request)


    # Results of second step in signup - invite co-workers
    @defer.inlineCallbacks
    def _signupInviteCoworkers(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if not authinfo.username:
            raise errors.Unauthorized()

        rawEmailIds = utils.getRequestArg(request, 'email', multiValued=True) or []
        d = people.invite(request, rawEmailIds)
        request.redirect('/feed')


    # We are currently in a private demo mode.
    # Signups => Notify when we are public
    # We categorize them by domains, so that we can rollout by domain.
    @defer.inlineCallbacks
    def _signup(self, request):
        if not self.thanksPage:
            self.thanksPage = static.File("public/thanks.html")

        emailId = utils.getRequestArg(request, "email")
        local, domain = emailId.split('@')
        yield db.insert(domain, "notifyOnRelease", '', emailId)
        self.thanksPage.render_GET(request)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addUser(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        emailId = utils.getRequestArg(request, 'email')
        localpart, domain = emailId.split("@")
        displayName = utils.getRequestArg(request, 'name')
        jobTitle = utils.getRequestArg(request, 'jobTitle')
        timezone = utils.getRequestArg(request, 'timezone')
        passwd = utils.getRequestArg(request, 'password', sanitize=False)
        pwdrepeat = utils.getRequestArg(request, 'pwdrepeat', sanitize=False)
        if not displayName or not jobTitle or not timezone or not passwd:
            raise errors.MissingParams()

        if passwd != pwdrepeat:
            raise errors.PasswordsNoMatch()

        args = {'emailId': emailId, 'view':'invite'}

        existingUser = yield db.get_count(emailId, "userAuth")
        if not existingUser:
            orgId = yield getOrgKey(domain)
            if not orgId:
                orgId = utils.getUniqueKey()
                domains = {domain:''}
                basic = {"name":domain, "type":"org"}
                yield db.batch_insert(orgId, "entities", {"basic":basic,"domains":domains})
                yield db.insert(domain, "domainOrgMap", '', orgId)

            userId = yield utils.addUser(emailId, displayName, passwd,
                                         orgId, jobTitle, timezone)
            authinfo.username = userId
            authinfo.organization = orgId
            authinfo.isAdmin = False

            yield db.remove(domain, "invitations", super_column=emailId)
            yield render(request, "signup.mako", **args)
        else:
            raise errors.InvalidRegistration()


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._signupCheckToken(request)
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
                d = self._signupInviteCoworkers(request)
            elif action == 'create':
                d = self._signupGotUserData(request)
            return self._epilogue(request, d)
        else:
            return self._epilogue(request)
