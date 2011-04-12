import PythonMagick
import imghdr
from hashlib            import md5

from twisted.python     import log
from twisted.internet   import defer
from twisted.web        import server, resource
from twisted.mail.smtp  import sendmail
from telephus.cassandra import ttypes
from email.mime.text    import MIMEText

import social.constants as constants
from social.base        import BaseResource
from social             import utils, Db, Config
from social.isocial     import IAuthInfo
from social.template    import render
from social.logging     import dump_args, profile

DEVMODE = Config.get('General', 'DevMode') == 'True'
DEVMODE = True
MAXFILESIZE = 4*1024*1024


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
    rootUrl = Config.get('General', 'Home')
    subject  = ''
    if username:
        subject = "%s has invited you to join Jujubi" %(username)
    else:
        subject = "Welcome to Jujubi"

    msg = MIMEText("%(subject)s."
            "Click on the link to activate your account. "
            "%(rootUrl)s/register?emailId=%(emailId)s&token=%(token)s"%(locals()))
    to_addr = 'praveen@synovel.com' if DEVMODE else emailId
    from_addr = "noreply@synovel.com"
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
        orgKey = yield utils.getCompanyKey(sender)
        cols = yield Db.get_slice(orgKey, "entities", super_column="domains")
        cols = utils.columnsToDict(cols)
        domains = cols.keys()

        defer.returnValue(inviteeDomain and inviteeDomain in domains)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _isValidToken(self, request, token, emailId):
        try:
            userKey = yield Db.get(emailId, "userAuth", "user")
            request.redirect("/signin")
        except:
            cols = yield Db.get_slice(emailId, "invitations")
            invitation = utils.columnsToDict(cols)
            if invitation.get("token", None) == token:
                yield render(request, "signup.mako", **request.args)
            else:
                raise Exception("Invalid Token")

    @profile
    @dump_args
    def render_GET(self, request):
        def errback(err):
            log.err(err)
            request.setResponseCode(500)
            request.finish()
        def callback(response):
            request.finish()

        segmentCount = len(request.postpath)
        if segmentCount == 0:
            emailId = utils.getRequestArg(request, "emailId")
            token = utils.getRequestArg(request, "token")
            d = self._isValidToken(request, token, emailId)
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        elif segmentCount == 1 and request.postpath[0]== 'signup':
            d =  render(request, "register.mako", **request.args)
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        elif segmentCount == 1 and request.postpath[0]== 'basic':
            d =  render(request, "signup-info.mako", **request.args)
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _sendInvitation(self, emailId, sender):
        cols = {}
        name = None
        token = utils.getRandomKey('username')
        cols['token'] = token

        if sender:
            cols = {'sender':sender}
            userinfo = yield Db.get_slice(sender, "entities", ["name"], super_column="basic")
            userinfo = utils.columnsToDict(userinfo)
            name = userinfo['name'] if userinfo.has_key('name') else None

        yield Db.batch_insert(emailId, "invitations", cols)
        yield send_email(emailId, token, name)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _signup(self, request):
        username = None
        emailId = utils.getRequestArg(request, 'emailId')
        sender = request.getSession(IAuthInfo).username
        try:
            mailid, domain = emailId.split("@")
        except ValueError, err:
            raise err

        if sender:
            validMailId = yield self._isValidMailId(domain, sender)
            if not validMailId:
                raise errors.InvalidEmailId()

        orgKey = yield getOrgKey(domain)
        if not orgKey:
            domains = {domain:''}
            basic = {"name":domain, "type":"org"}
            orgKey = utils.getUniqueKey()
            yield Db.batch_insert(orgKey, "entities", {"basic": basic, "domains":domains})
            yield Db.insert(domain, "domainOrgMap", '', orgKey)

        # TODO: check if email is already registered

        yield self._sendInvitation(emailId, sender)
        if not sender:
            request.redirect('/signin')

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addUser(self, request):
        emailId = utils.getRequestArg(request, 'emailId')
        domain = emailId.split("@")[1]
        passwd = utils.getRequestArg(request, 'password')
        username = utils.getRequestArg(request, 'name')

        username = username if username else emailId
        existingUser = yield Db.get_count(emailId, "userAuth")
        if not existingUser:
            orgKey = yield getOrgKey(domain)
            userKey = yield utils.addUser(emailId, username, passwd, orgKey)
            yield Db.remove(emailId, "invitations")

            cols = yield Db.get_slice(orgKey, "entities", ["admins"])
            if not cols:
                yield Db.insert(orgKey, "entities", "", userKey, "admins")

        else:
            raise errors.ExistingUser

    @profile
    @dump_args
    def render_POST(self, request):

        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self._signup(request)
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            def callback(response):
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET

        elif segmentCount == 1 and request.postpath[0]== 'create':
            d = self._addUser(request)
            def callback(response):
                request.redirect('/profile/edit')
                request.finish()
            def errback(err):
                log.err(err)
                request.write("Error")
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        else:
            return resource.NoResource("Page not Found")
