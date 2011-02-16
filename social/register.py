from hashlib import md5

from twisted.python import log
from twisted.internet import defer
from twisted.web import server
from twisted.mail.smtp import sendmail
from telephus.cassandra import ttypes

from social.base import BaseResource
from social import utils, Db, Config
from social.auth import IAuthInfo
from social.template import render
from email.mime.text import MIMEText

DEVMODE = Config.get('General', 'DevMode') == 'True'
DEVMODE = True

def getOrgKey(org):
    return org

@defer.inlineCallbacks
def send_email(emailId, token, username):
    rootUrl = Config.get('General', 'Home')
    msg = MIMEText("%(username)s has Invited you to join social network."
            "Click on the link to activate your account. "
            "%(rootUrl)s/register?emailId=%(emailId)s&token=%(token)s"%(locals()))
    to_addr = 'praveen@synovel.com' if DEVMODE else emailId
    from_addr = "noreply@synovel.com"
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = "%s has invited you to join Jujubi"%(username)
    msg = msg.as_string()

    host = Config.get('SMTP', 'Host')
    yield sendmail(host, from_addr, to_addr, msg)


def _validateEmailId(emailId, username):
    companyName = utils.getCompanyKey(username)
    inviteeCompanyName = emailId.split("@")[1] if len(emailId.split('@'))==2 else None
    return inviteeCompanyName == companyName


class RegisterResource(BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _isValidToken(self, request, token, emailId):
        userKey = utils.toUserKey(emailId)
        existingUser = yield Db.get_count(userKey, "userAuth")
        if not existingUser:
            cols = yield Db.get_slice(emailId, "invitations")
            invitation = utils.columnsToDict(cols)
            if invitation.get("token", None) == token:
                yield render(request, "signup.mako", **request.args)
            else:
                raise Exception("Invalid Token")
        else:
            request.redirect("/signin")

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

    @defer.inlineCallbacks
    def _sendInvitation(self, emailId, username):
        cols = {}
        if username:
            cols = {'sender':username}
        token = utils.getRandomKey('username')
        cols['token'] = token
        yield Db.batch_insert(emailId, "invitations", cols)
        yield send_email(emailId, token, username)

    @defer.inlineCallbacks
    def _signup(self, request):

        username = None
        emailId = utils.getRequestArg(request, 'emailId')
        id, org = emailId.split("@")
        orgKey = getOrgKey(org)
        try:
            yield Db.get(orgKey, "orgs", super_column="meta")
        except ttypes.NotFoundException:
            meta = {'name': org}
            yield Db.batch_insert(orgKey, "orgs", {'meta':meta})
        username = request.getSession(IAuthInfo).username
        if username and not _validateEmailId(emailId, username):
                raise errors.InvalidEmailId
        yield self._sendInvitation(emailId, username)
        if not username:
            request.redirect('/signin')

    @defer.inlineCallbacks
    def _addUser(self, request):
        emailId = utils.getRequestArg(request, 'emailId')
        org = emailId.split("@")[1]
        orgKey = org
        passwd = utils.getRequestArg(request, 'password')
        username = utils.getRequestArg(request, 'name')

        username = username if username else emailId
        userKey = utils.toUserKey(emailId)
        existingUser = yield Db.get_count(userKey, "userAuth")
        if not existingUser:
            orgKey = getOrgKey(org)
            count = yield Db.get_count(orgKey, "orgUsers")
            isAdmin = not count
            if isAdmin:
                yield Db.insert(orgKey, "orgs", "", userKey, "admins")

            yield Db.batch_insert(userKey, "userAuth", {
                                        "passwordHash": md5(passwd).hexdigest(),
                                         "isAdmin": str(isAdmin),
                                         "org": orgKey})
            yield Db.batch_insert(userKey, "users", {'basic': {'name': username}})
            yield Db.insert(orgKey, "orgUsers", '', userKey)
            yield Db.remove(emailId, "invitations")


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
                request.redirect('/signin')
                request.finish()
            def errback(err):
                log.err(err)
                request.write("Error adding user")
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
