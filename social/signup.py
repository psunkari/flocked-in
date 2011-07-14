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
from social             import utils, db, config, people, errors, _
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import dump_args, profile


class InvalidRegistration(errors.BaseError):
    pass


class PasswordsNoMatch(errors.BaseError):
    pass


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
            defer.returnValue(None)

        try:
            yield db.get(emailId, "userAuth", "user")
            defer.returnValue(None)
        except: pass
        try:
            local, domain = emailId.split('@')
            sender = yield db.get(domain, "invitations", token, emailId)
            sender = sender.column.value
        except ttypes.NotFoundException, e:
            defer.returnValue(None)

        defer.returnValue(sender)

    # Link that is sent in mails.
    @defer.inlineCallbacks
    def _signupCheckToken(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username:
            raise errors.InvalidRequest(_("Another user is currently signed-in.  Please signout and then click the invitation link"))

        emailId = utils.getRequestArg(request, "email")
        token = utils.getRequestArg(request, "token")

        valid = yield self._isValidToken(emailId, token)
        if not valid:
            raise InvalidRegistration("The invite is not valid anymore.  Already registered?")

        args = {'emailId': emailId, 'token': token, 'view': 'userinfo'}
        yield render(request, "signup.mako", **args)

    # Results of first step in signup - basic user information
    @defer.inlineCallbacks
    def _signupGotUserData(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if authinfo.username:
            raise errors.InvalidRequest(_("Another user is currently signed-in.  Please signout and then click the invitation link"))

        emailId = utils.getRequestArg(request, "email")
        token = utils.getRequestArg(request, "token")

        valid = yield self._isValidToken(emailId, token)
        if not valid:
            raise InvalidRegistration("The invite is not valid anymore.  Already registered?")

        yield self._addUser(request)


    # Results of second step in signup - invite co-workers
    @defer.inlineCallbacks
    def _signupInviteCoworkers(self, request):
        authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        if not authinfo.username:
            raise errors.Unauthorized("You need to login before sending invitations to other users")

        rawEmailIds = utils.getRequestArg(request, 'email', multiValued=True) or []
        stats = yield people.invite(request, rawEmailIds)
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
        emailId = utils.getRequestArg(request, 'email')
        existingUser = db.get_count(emailId, "userAuth")

        localpart, domain = emailId.split("@")
        displayName = utils.getRequestArg(request, 'name')
        jobTitle = utils.getRequestArg(request, 'jobTitle')
        timezone = utils.getRequestArg(request, 'timezone')
        passwd = utils.getRequestArg(request, 'password', sanitize=False)
        pwdrepeat = utils.getRequestArg(request, 'pwdrepeat', sanitize=False)
        if not displayName or not jobTitle or not timezone or not passwd:
            raise errors.MissingParams([_("All fields are required to create the user")])

        if passwd != pwdrepeat:
            raise PasswordsNoMatch()

        args = {'emailId': emailId, 'view':'invite'}

        existingUser = yield existingUser
        if not existingUser:
            authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
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

            cols = yield db.get_slice(domain, "invitations", [emailId])
            cols = utils.supercolumnsToDict(cols)
            userIds = cols.get(emailId, {}).values()
            if userIds:
                db.batch_remove({'invitationsSent':userIds}, names=[emailId])

            yield db.remove(domain, "invitations", super_column=emailId)
            yield render(request, "signup.mako", **args)
        else:
            raise InvalidRegistration("A user with this e-mail already exists! Already registered?")


    @defer.inlineCallbacks
    def _block(self, request, blockType):
        token = utils.getRequestArg(request, "token")
        emailId = utils.getRequestArg(request, "email")
        sender = yield self._isValidToken(emailId, token)

        if blockType == "all":
            yield db.insert(emailId, "doNotSpam", "", "*")
        elif blockType == "sender":
            yield db.insert(emailId, "doNotSpam", "", sender)

        # The invitation is not removed.
        # This is to ensure that the sender can still whom he invited and that
        # the invited person did not join flocked.in

        args = {'view': 'block', 'blockType': blockType, 'emailId': emailId}
        yield render(request, "signup.mako", **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._signupCheckToken(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == 'blockSender':
                d = self._block(request, "sender")
            elif action == 'blockAll':
                d = self._block(request, "all")
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
