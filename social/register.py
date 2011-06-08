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


@profile
@defer.inlineCallbacks
@dump_args
def send_email(emailId, token, username):
    rootUrl = Config.get('General', 'URL')
    subject  = ''
    if username:
        subject = "%s has invited you to join Jujubi" %(username)
    else:
        subject = "Welcome to Jujubi"

    msg = MIMEText("%(subject)s."
            "Click on the link to activate your account. "
            "%(rootUrl)s/register?emailId=%(emailId)s&token=%(token)s"%(locals()))
    #to_addr = 'praveen@synovel.com' if DEVMODE else emailId
    to_addr = 'praveen@synovel.com'
    from_addr = "social@synovel.com"
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg = msg.as_string()

    host = Config.get('SMTP', 'Host')
    yield sendmail(host, from_addr, to_addr, msg)



class RegisterResource(BaseResource):
    isLeaf = True

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
        except:
            cols = yield Db.get_slice(emailId, "invitations")
            invitation = utils.columnsToDict(cols)
            if token and invitation.get("token", None) == token:
                args = request.args
                args['emailId']=emailId
                args['view'] = 'userinfo'
                yield render(request, "signup.mako", **args)
            else:
                raise errors.InvalidToken()


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _sendInvitation(self, emailId, sender):
        cols = {}
        name = None
        token = utils.getRandomKey('username')
        cols['token'] = token
        if sender:
            senderId = yield Db.get(sender, "userAuth", 'user')
            senderId = senderId.column.value
            cols['sender']= senderId
            userinfo = yield Db.get_slice(senderId, "entities", ["name"], super_column="basic")
            userinfo = utils.columnsToDict(userinfo)
            name = userinfo['name'] if userinfo.has_key('name') else None
        yield Db.batch_insert(emailId, "invitations", cols)
        send_email(emailId, token, name)


    @defer.inlineCallbacks
    def _invite(self, request):
        deferreds = []
        validEmailIds = []

        emailIds = request.args.get('emailId', [])
        sender = utils.getRequestArg(request, 'sender')
        submit = utils.getRequestArg(request, 'submit')
        skip = utils.getRequestArg(request, 'skip')

        for emailId in emailIds:
            if len(emailId.split('@'))==2:
                domain = emailId.split('@')[1]
                if sender:
                    valid = yield self._isValidMailId(domain, sender)
                else:
                    valid = True
                if valid:
                    if Config.has_option("General", "WhiteListMode") and \
                        Config.get("General", "WhiteListMode") == "True":
                        if  domain in whitelist and domain not in blacklist:
                            validEmailIds.append(emailId)
                    else:
                        validEmailIds.append(emailId)
                else:
                    raise errors.InvalidEmailId()
        for emailId in validEmailIds:
            d =  self._sendInvitation(emailId, sender)
            deferreds.append(d)

        prevPage = request.getCookie("page")
        if prevPage == "register":
            request.redirect('/people?type=all')
        elif not prevPage:
            request.redirect('/signin')
        else:
            request.redirect('/'+prevPage)

        # instead of redirecting, render a mesg saying that a mail is sent to the given emailIds.

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addUser(self, request):
        def setCookie(userId, orgId=None):
            session = request.getSession()
            session.sessionTimeout = 14400  # Timeout of 4 hours
            authinfo = session.getComponent(IAuthInfo)
            authinfo.username = userId
            authinfo.organization = orgId
            authinfo.isAdmin = False



        landing = not self._ajax
        emailId = utils.getRequestArg(request, 'emailId')
        domain = emailId.split("@")[1]
        passwd = utils.getRequestArg(request, 'password')
        passwd1 = utils.getRequestArg(request, 'password1')
        username = utils.getRequestArg(request, 'name')
        title = utils.getRequestArg(request, 'jobTitle')
        timezone = utils.getRequestArg(request, 'timezone')
        args= {'emailId': emailId, 'view':'invite'}

        if passwd != passwd1:
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
            yield Db.remove(emailId, "invitations")
            setCookie(userKey, orgKey)
            yield render(request, "signup.mako", **args)

        else:
            request.redirect('/signup')
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
        if segmentCount == 0 or \
           segmentCount == 1 and request.postpath[0]== 'invite' :
            d = self._invite(request)
        elif segmentCount == 1 and request.postpath[0]== 'create':
            d = self._addUser(request)
        else:
            return resource.NoResource("Page not Found")

        return self._epilogue(request, d)
