import PythonMagick
import imghdr
import time
from datetime           import datetime


from twisted.internet   import defer
from twisted.web        import server, resource, static
from twisted.mail.smtp  import sendmail
from twisted.cred.error import Unauthorized
from telephus.cassandra import ttypes
from email.mime.text    import MIMEText

import social.constants as constants
from social.base        import BaseResource
from social             import utils, db, config, people, errors, _
from social             import notifications, blacklist
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import dump_args, profile, log
from social.errors      import PermissionDenied, MissingParams


class InvalidRegistration(errors.BaseError):
    pass


class PasswordsNoMatch(errors.BaseError):
    pass


class InvalidEmailId(errors.BaseError):
    pass


class DomainBlacklisted(errors.BaseError):
    pass


@profile
@defer.inlineCallbacks
@dump_args
def getOrgKey(domain):
    cols = yield db.get_slice(domain, "domainOrgMap")
    cols = utils.columnsToDict(cols)
    orgKey = cols.keys()[0] if cols else None
    defer.returnValue(orgKey)


@defer.inlineCallbacks
def _sendmailResetPassword(email, token):
    rootUrl = config.get('General', 'URL')
    brandName = config.get('Branding', 'Name')

    body = "A request was received to reset the password "\
           "for %(email)s on %(brandName)s.\nTo change the password please click the following "\
           "link, or paste it in your browser.\n\n%(resetPasswdUrl)s\n\n"\
           "This link is valid for 24hours only.\n"\
           "If you did not request this email there is no need for further action\n"

    resetPasswdUrl = "%(rootUrl)s/password/resetPassword?email=%(email)s&token=%(token)s"%(locals())
    args = {"brandName": brandName, "rootUrl": rootUrl,
            "resetPasswdUrl": resetPasswdUrl, "email":email}
    subject = "[%(brandName)s] Reset Password requested for %(email)s" %(locals())
    htmlBody = getBlock("emails.mako", "forgotPasswd", **args)
    textBody = body %(locals())
    yield utils.sendmail(email, subject, textBody, htmlBody)


@defer.inlineCallbacks
def _getResetPasswordTokens(email):
    tokens = []
    deleteTokens = []
    validEmail = False
    leastTimestamp = time.time()
    cols = yield db.get_slice(email, "userAuth")
    for col in cols:
        if col.column.name.startswith('resetPasswdToken'):
            tokens.append(col.column.value)
            deleteTokens.append(col.column.name)
            if col.column.timestamp/1e6 < leastTimestamp :
                leastTimestamp = col.column.timestamp/1e6
        else:
            validEmail = True
    defer.returnValue((validEmail, tokens, deleteTokens, leastTimestamp))


@defer.inlineCallbacks
def _sendSignupInvitation(emailId):
    if len(emailId.split('@')) != 2:
        raise InvalidEmailId()

    mailId, domain = emailId.split('@')
    if domain in blacklist:
        raise DomainBlacklisted()

    rootUrl = config.get('General', 'URL')
    brandName = config.get('Branding', 'Name')
    signature = "Flocked-in Team.\n\n\n\n"

    myOrgId = yield getOrgKey(domain)
    if myOrgId:
        entities = yield db.get_slice(myOrgId, "entities", ["basic"])
        myOrg =  utils.supercolumnsToDict(entities)
        orgName = myOrg['basic']['name']
    else:
        orgName =  domain

    existing = yield db.get_slice(emailId, "userAuth", ["user"])
    existing = utils.columnsToDict(existing)
    if existing and existing.get('user', ''):
        subject = "[%s] Account exists" % (brandName)
        body = "You already have an account on %(brandName)s.\n"\
               "Please visit %(rootUrl)s/signin to sign-in.\n\n"
        textBody = (body + signature) % locals()
        htmlBody = getBlock("emails.mako", "accountExists", **locals())
    else:
        subject = "Welcome to %s" %(brandName)
        body = "Please click the following link to join %(orgName)s network on %(brandName)s\n"\
               "%(activationUrl)s\n\n"
        activationTmpl = "%(rootUrl)s/signup?email=%(emailId)s&token=%(token)s"

        token = utils.getRandomKey()
        insert_d = db.insert(domain, "invitations", emailId, token, emailId)
        activationUrl = activationTmpl % locals()
        textBody = (body + signature) % locals()
        htmlBody = getBlock("emails.mako", "signup", **locals())
        yield insert_d

    yield utils.sendmail(emailId, subject, textBody, htmlBody)


class SignupResource(BaseResource):
    isLeaf = True
    requireAuth = False
    thanksPage = None
    invalidEmailPage = None

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


    @defer.inlineCallbacks
    def _signup(self, request):
        if not self.thanksPage:
            self.thanksPage = static.File("public/thanks.html")
        if not self.invalidEmailPage:
            self.invalidEmailPage = static.File("public/invalid-email.html")

        emailId = utils.getRequestArg(request, "email")

        try:
            yield _sendSignupInvitation(emailId)
            self.thanksPage.render_GET(request)
        except (InvalidEmailId, DomainBlacklisted), e:
            self.invalidEmailPage.render_GET(request)

        defer.returnValue(None)


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
            yield request._saveSessionToDB()

            cols = yield db.get_slice(domain, "invitations", [emailId])
            cols = utils.supercolumnsToDict(cols)

            userIds = cols.get(emailId, {}).values()
            if userIds:
                db.batch_remove({'invitationsSent':userIds}, names=[emailId])

            yield db.remove(domain, "invitations", super_column=emailId)
            yield render(request, "signup.mako", **args)

            # Notify all invitees about this user.
            token = utils.getRequestArg(request, "token")
            acceptedInvitationSender = cols.get(emailId, {}).get(token)
            otherInvitees = [x for x in userIds
                             if x not in (acceptedInvitationSender, emailId)]

            cols = yield db.multiget_slice(userIds+[orgId, userId], "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(cols)
            data = {"entities": entities, 'orgId': orgId}

            yield notifications.notify([acceptedInvitationSender], ":IA", userId, **data)
            yield notifications.notify(otherInvitees, ":NU", userId, **data)
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

    @defer.inlineCallbacks
    def resetPassword(self, request):
        email = utils.getRequestArg(request, 'email')
        token = utils.getRequestArg(request, 'token')
        passwd = utils.getRequestArg(request, 'password', False)
        pwdrepeat = utils.getRequestArg(request, 'pwdrepeat', False)

        if not (email and token and passwd and pwdrepeat):
            raise MissingParams(['Email', 'Password Reset Token'])

        if (passwd != pwdrepeat):
            raise errors.PasswordsNoMatch()

        validEmail, tokens, deleteTokens, leastTimestamp = yield _getResetPasswordTokens(email)
        if validEmail:
            if token not in tokens:
                raise PermissionDenied("Invalid token. <a href='/password/resend?email=%s'>Click here</a> to reset password"%(email))
            yield db.insert(email, "userAuth", utils.hashpass(passwd), 'passwordHash')
            yield db.batch_remove({"userAuth": [email]}, names=deleteTokens)
        request.redirect('/signin')
        # XXX: notify user

    @defer.inlineCallbacks
    def request_resetPassword(self, request):
        email = utils.getRequestArg(request, 'email')

        if not email:
            raise MissingParams([''])

        now = time.time()
        validEmail, tokens, deleteTokens, leastTimestamp = yield _getResetPasswordTokens(email)
        if len(tokens) >= 10:
            delta = datetime.fromtimestamp(leastTimestamp + 86399) - datetime.fromtimestamp(now)
            hours = 1 + delta.seconds/3600
            raise PermissionDenied('We detected ususual activity from your account.<br/>  Click the link sent to your emailId to reset password or wait for %s hours before you retry'%(hours))

        if validEmail:
            token = utils.getRandomKey()
            yield db.insert(email, "userAuth", token, 'resetPasswdToken:%s'%(token), ttl=86400)
            yield _sendmailResetPassword(email, token)

        args = {"view": "forgotPassword-post"}
        yield render(request, "signup.mako", **args)

    @defer.inlineCallbacks
    def renderForgotPassword(self, request):
        args = {"view": "forgotPassword"}
        yield render(request, "signup.mako",  **args)

    @defer.inlineCallbacks
    def renderResetPassword(self, request):
        email = utils.getRequestArg(request, 'email')
        token = utils.getRequestArg(request, 'token')

        if not (email and token):
            raise MissingParams([''])

        validEmail, tokens, deleteTokens, leastTimestamp = yield _getResetPasswordTokens(email)
        # XXX: If not validEmail, send invite to the user
        if not validEmail or token not in tokens:
            raise PermissionDenied("Invalid token. <a href='/password/resend?email=%s'>Click here</a> to reset password"%(email))
        args = {"view": "resetPassword", "email": email, "token": token}
        yield render(request, "signup.mako",  **args)

    @defer.inlineCallbacks
    def _verifyProfile(self, request):
        email = utils.getRequestArg(request, 'email')
        token = utils.getRequestArg(request, 'token')

        if not (email and token):
            raise MissingParams(['Email', 'Account Verification Token'])

        cols = yield db.get_slice(email, "userAuth", ["reactivateToken", "isFlagged"])
        cols = utils.columnsToDict(cols)
        if cols.has_key("isFlagged"):
            storedToken = cols.get("reactivateToken", None)
            if storedToken == token:
                yield db.batch_remove({"userAuth": [email]},
                                    names=["reactivateToken", "isFlagged"])

        request.redirect('/signin')

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        prepath = []
        try:
            prepath = request.prepath
        except:
            pass
        d = None
        if segmentCount == 0:
            d = self._signupCheckToken(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if prepath and prepath[0] == 'password':
                if action == 'resetPassword':
                    d = self.renderResetPassword(request)
                elif action == 'forgotPassword':
                    d = self.renderForgotPassword(request)
                elif action == 'resend':
                    d = self.request_resetPassword(request)
                elif action == 'verify':
                    d = self._verifyProfile(request)
            else:
                if action == 'blockSender':
                    d = self._block(request, "sender")
                elif action == 'blockAll':
                    d = self._block(request, "all")
        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        prepath = []
        try:
            prepath = request.prepath
        except:
            pass

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
            if prepath and prepath[0] == 'password':
                if action == 'resetPassword':
                    d = self.resetPassword(request)
                elif action == 'forgotPassword':
                    d = self.request_resetPassword(request)
            else:
                if action == 'invite' :
                    d = self._signupInviteCoworkers(request)
                elif action == 'create':
                    d = self._signupGotUserData(request)
            return self._epilogue(request, d)
        else:
            return self._epilogue(request)
