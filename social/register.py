import PythonMagick
import imghdr
from hashlib            import md5

from twisted.python     import log
from twisted.internet   import defer
from twisted.web        import server
from twisted.mail.smtp  import sendmail
from telephus.cassandra import ttypes
from email.mime.text    import MIMEText

import social.constants as constants
from social.base        import BaseResource
from social             import utils, Db, Config
from social.auth        import IAuthInfo
from social.template    import render

DEVMODE = Config.get('General', 'DevMode') == 'True'
DEVMODE = True
MAXFILESIZE = 4*1024*1024

def _getImageFileFormat(data):
    imageType = imghdr.what(None, data)
    if imageType:
        return imageType.lower()
    return imageType

@defer.inlineCallbacks
def getOrgKey(domain):
    cols = yield Db.get_slice(domain, "domainOrgMap")
    cols = utils.columnsToDict(cols)
    orgKey = cols.keys()[0] if cols else None
    defer.returnValue(orgKey)


@defer.inlineCallbacks
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


    @defer.inlineCallbacks
    def _isValidMailId(self, inviteeDomain, sender):
        orgKey = yield utils.getCompanyKey(sender)
        cols = yield Db.get_slice(orgKey, "orgs", super_column="domains")
        cols = utils.columnsToDict(cols)
        domains = cols.keys()

        defer.returnValue(inviteeDomain and inviteeDomain in domains)


    @defer.inlineCallbacks
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


    @defer.inlineCallbacks
    def _sendInvitation(self, emailId, sender):
        cols = {}
        name = None
        token = utils.getRandomKey('username')
        cols['token'] = token

        if sender:
            cols = {'sender':sender}
            userinfo = yield Db.get_slice(sender, "users", ["name"], super_column="basic")
            userinfo = utils.columnsToDict(userinfo)
            name = userinfo['name'] if userinfo.has_key('name') else None

        yield Db.batch_insert(emailId, "invitations", cols)
        yield send_email(emailId, token, name)

    @defer.inlineCallbacks
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
                raise errors.InvalidEmailId

        orgKey = yield getOrgKey(domain)
        if not orgKey:
            domains = {domain:''}
            meta = {"name":domain}
            orgKey = utils.getUniqueKey()
            yield Db.batch_insert(orgKey, "orgs", {"meta": meta, "domains":domains})
            yield Db.insert(domain, "domainOrgMap", '', orgKey)

        # TODO: check if email is already registered

        yield self._sendInvitation(emailId, sender)
        if not sender:
            request.redirect('/signin')

    @defer.inlineCallbacks
    def _addUser(self, request):
        emailId = utils.getRequestArg(request, 'emailId')
        domain = emailId.split("@")[1]
        passwd = utils.getRequestArg(request, 'password')
        username = utils.getRequestArg(request, 'name')

        username = username if username else emailId
        existingUser = yield Db.get_count(emailId, "userAuth")
        if not existingUser:
            orgKey = yield getOrgKey(domain)
            userKey = utils.getUniqueKey()
            count = yield Db.get_count(orgKey, "orgUsers")
            isAdmin = not count
            if isAdmin:
                yield Db.insert(orgKey, "orgs", "", userKey, "admins")

            yield Db.batch_insert(emailId, "userAuth", {
                                        "passwordHash": md5(passwd).hexdigest(),
                                         "isAdmin": str(isAdmin),
                                         "org": orgKey,
                                         "user": userKey})
            yield Db.batch_insert(userKey, "users", {'basic': {'name': username, 'org':orgKey}})
            yield Db.insert(orgKey, "orgUsers", '', userKey)
            yield Db.remove(emailId, "invitations")
        else:
            raise errors.ExistingUser

    @defer.inlineCallbacks
    def _addUserBasic(self, request):
        def getUserInfo(userInfo, sc, cn, request):
            value = utils.getRequestArg(request, cn)
            if value:
                if not sc in userInfo:
                    userInfo[sc]={}
                userInfo[sc][cn]=value


        userInfo = {}
        emailId = utils.getRequestArg(request, "emailId")
        cols = yield Db.get_slice(emailId, "userAuth", ["user"])
        cols = utils.columnsToDict(cols)
        userKey = cols["user"]
        for cn in ("jobTitle", "location", "desc", "name"):
            getUserInfo(userInfo, "basic", cn, request)
        if "basic" in userInfo:
            basic_acl = utils.getRequestArg(request, "basic_acl")
            userInfo["basic"]["acl"] = basic_acl

        dp = utils.getRequestArg(request, "dp")
        avatar_acl = utils.getRequestArg(request, "avatar_acl")
        if dp:
            imageFormat = _getImageFileFormat(dp)
            if imageFormat not in constants.SUPPORTED_IMAGE_TYPES:
                raise errors.InvalidImageType
            from base64 import b64encode
            blob =  PythonMagick.Blob(dp)
            try:
                image = PythonMagick.Image(blob)
            except Exception as e:
                raise e

            small = PythonMagick.Blob()
            profile = PythonMagick.Blob()
            conv = PythonMagick.Blob()
            image.scale(constants.PROFILE)
            image.write(profile)
            image.scale(constants.CONV)
            image.write(conv)
            image.scale(constants.COMM)
            image.write(small)
            userInfo["avatar"]={}
            userInfo["avatar"]["large"] = "%s:%s"%(imageFormat, profile.base64())
            userInfo["avatar"]["medium"] = "%s:%s"%(imageFormat, conv.base64())
            userInfo["avatar"]["small"] = "%s:%s"%(imageFormat, small.base64())
            userInfo["avatar"]["orig"] = "%s:%s"%(imageFormat, blob.base64())
            userInfo["avatar"]["acl"] = avatar_acl

        expertise = utils.getRequestArg(request, "expertise")
        expertise_acl = utils.getRequestArg(request, "expertise_acl")
        if expertise:
            userInfo["expertise"] = {}
            userInfo["expertise"][expertise]=""
            userInfo["expertise"]["acl"]=expertise_acl

        language = utils.getRequestArg(request, "language")
        lr = utils.getRequestArg(request, "language_r") == "on"
        ls = utils.getRequestArg(request, "language_s") == "on"
        lw = utils.getRequestArg(request, "language_w") == "on"
        language_acl = utils.getRequestArg(request, "language_acl")
        if language:
            userInfo["languages"]= {}
            userInfo["languages"][language]= "%(lr)s/%(lw)s/%(ls)s" %(locals())
            userInfo["languages"]["acl"] = language_acl

        c_email = utils.getRequestArg(request, "c_email")
        c_im = utils.getRequestArg(request, "c_im")
        c_phone = utils.getRequestArg(request, "c_phone")
        contacts_acl = utils.getRequestArg(request, "contacts_acl")

        if any([c_email, c_im, c_phone]):
            userInfo["contact"] = {}
            userInfo["contact"]["acl"] = contacts_acl

        if c_email:
            userInfo["contact"]["mail"] = c_email
        if c_im:
            userInfo["contact"]["im"] = c_im
        if c_phone:
            userInfo["contact"]["phone"] = c_phone


        interests = utils.getRequestArg(request, "interests")
        interests_acl = utils.getRequestArg(request, "interests_acl")
        if interests:
            userInfo["interests"]= {}
            userInfo["interests"][interests]= interests
            userInfo["interests"]["acl"] = interests_acl

        p_email = utils.getRequestArg(request, "p_email")
        p_phone = utils.getRequestArg(request, "p_phone")
        hometown = utils.getRequestArg(request, "hometown")
        personal_acl = utils.getRequestArg(request, "personal_acl")
        if any([p_email, p_phone, hometown]):
            userInfo["personal"]={}
        if p_email:
            userInfo["personal"]["email"] = p_email
        if p_phone:
            userInfo["personal"]["phone"] = p_phone
        if hometown:
            userInfo["personal"]["currentCity"] = hometown
        if userInfo:
            yield Db.batch_insert(userKey, "users", userInfo)


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
                request.redirect('/register/basic?emailId=%s'%(utils.getRequestArg(request, "emailId")))
                request.finish()
            def errback(err):
                log.err(err)
                request.write("Error adding user")
                request.setResponseCode(500)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
        elif segmentCount == 1 and request.postpath[0]== 'basic':
            headers = request.requestHeaders
            if int(headers.getRawHeaders("content-length", [0])[0]) > MAXFILESIZE:
                request.redirect('/register/basic?emailId=%s'%(utils.getRequestArg(request, "emailId")))
                request.write("File too large")
                request.finish()
            d = self._addUserBasic(request)
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
