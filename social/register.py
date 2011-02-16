from hashlib import md5

from twisted.python import log
from twisted.internet import defer
from twisted.web import server
from twisted.mail.smtp import sendmail

from social.base import BaseResource
from social import utils, Db, Config
from social.auth import IAuthInfo
from social.template import render
from email.mime.text import MIMEText

DEVMODE = Config.get('General', 'DevMode') == 'True'


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
        cols = yield Db.get_slice(emailId, "invitations")
        invitation = utils.columnsToDict(cols)
        if invitation.get("token", None) == token:
            yield render(request, "signup.mako", **request.args)
        else:
            raise Exception("Invalid Token")

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            emailId = utils.getRequestArg(request, "emailId")
            token = utils.getRequestArg(request, "token")
            d = self._isValidToken(request, token, emailId)
            def errback(err):
                log.err(err)
                request.setResponseCode(500)
                request.finish()
            def callback(response):
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        else:
            request.finish()
            return ""

    @defer.inlineCallbacks
    def _sendInvitation(self, emailId, username):
        cols = {'sender':username}
        token = utils.getRandomKey('username')
        cols['token'] = token
        yield Db.batch_insert(emailId, "invitations", cols)
        yield send_email(emailId, token, username)


    def render_POST(self, request):

        segmentCount = len(request.postpath)
        if segmentCount == 0:

            emailId = utils.getRequestArg(request, 'emailId')
            username = request.getSession(IAuthInfo).username
            if not _validateEmailId(emailId, username):
                request.setResponseCode(400, "Invalid EmailId")
                return ""
            else:
                d = self._sendInvitation(emailId, username)
                def errback(err):
                    log.err(err)
                    request.setResponseCode(500)
                    request.finish()
                def callback(response):
                    request.finish()
                d.addCallbacks(callback, errback)
                return server.NOT_DONE_YET
        elif segmentCount == 1 and request.postpath[0]== 'create':
            emailId = utils.getRequestArg(request, 'emailId')
            passwd = utils.getRequestArg(request, 'password')
            username = utils.getRequestArg(request, 'name')

            username = username if username else emailId
            userKey = utils.toUserKey(emailId)
            d1 = Db.insert(userKey, "userAuth", md5(passwd).hexdigest(), 'passwordHash')
            d2 = Db.batch_insert(userKey, "users", {
                                                'basic': {
                                                    'name': username
                                                        }
                                                    })
            request.redirect('/signin')
            request.finish()
            return server.NOT_DONE_YET




