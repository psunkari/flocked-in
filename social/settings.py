import PythonMagick
import imghdr
import uuid
from random                 import sample

from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social                 import db, utils, base, plugins, _, __
from social                 import constants, feed, errors
from social.logging         import dump_args, profile
from social.isocial         import IAuthInfo


@defer.inlineCallbacks
def deleteAvatarItem(entity, isLogo=False):
    entity = yield db.get_slice(entity, "entities", ["basic"])
    entity = utils.supercolumnsToDict(entity)
    itemId = None
    imgFmt = None
    col = None
    if not entity:
        defer.returnValue(None)
    if isLogo:
        col = entity["basic"].get("logo", None)
    else:
        col = entity["basic"].get("avatar", None)
    if col:
        imgFmt, itemId = col.split(":")
    if itemId:
        yield db.remove(itemId, "items")


@profile
@defer.inlineCallbacks
@dump_args
def saveAvatarItem(entityId, data, isLogo=False):
    imageFormat = _getImageFileFormat(data)
    if imageFormat not in constants.SUPPORTED_IMAGE_TYPES:
        raise errors.InvalidFileFormat("The image format is not supported")

    try:
        original = PythonMagick.Blob(data)
        image = PythonMagick.Image(original)
    except Exception as e:
        raise errors.InvalidFileFormat("Invalid image format")

    medium = PythonMagick.Blob()
    small = PythonMagick.Blob()
    large = PythonMagick.Blob()
    largesize = constants.LOGO_SIZE_LARGE if isLogo else constants.AVATAR_SIZE_LARGE
    mediumsize = constants.LOGO_SIZE_MEDIUM if isLogo else constants.AVATAR_SIZE_MEDIUM
    smallsize = constants.LOGO_SIZE_SMALL if isLogo else constants.AVATAR_SIZE_SMALL

    image.scale(largesize)
    image.write(large)
    image.scale(mediumsize)
    image.write(medium)
    image.scale(smallsize)
    image.write(small)

    itemId = utils.getUniqueKey()
    item = {
        "meta": {"owner": entityId, "acl": "company", "type": "image"},
        "avatar": {
            "format": imageFormat,
            "small": small.data, "medium": medium.data,
            "large": large.data, "original": original.data
        }}
    yield db.batch_insert(itemId, "items", item)
    #delete older image if any;
    yield deleteAvatarItem(entityId, isLogo)

    defer.returnValue("%s:%s" % (imageFormat, itemId))


@profile
@dump_args
def _getImageFileFormat(data):
    imageType = imghdr.what(None, data)
    if imageType:
        return imageType.lower()
    return imageType


class SettingsResource(base.BaseResource):
    isLeaf = True
    resources = {}

    @defer.inlineCallbacks
    def _changePassword(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        curr_passwd = utils.getRequestArg(request, "curr_passwd", sanitize=False)
        passwd1 = utils.getRequestArg(request, "passwd1", sanitize=False)
        passwd2 = utils.getRequestArg(request, "passwd2", sanitize=False)

        yield self._render(request)

        args["errorMsg"] = ""
        if not curr_passwd:
            args["errorMsg"] = "Please enter your current password."
        if passwd1 != passwd2:
            args["errorMsg"] = "New passwords don't match."

        cols = yield db.get(myKey, "entities", "emailId", "basic")
        emailId = cols.column.value
        col = yield db.get(emailId, "userAuth", "passwordHash")
        passwdHash = col.column.value
        if curr_passwd and passwdHash != utils.md5(curr_passwd):
            args["errorMsg"] ="Incorrect Password"

        if args["errorMsg"]:
            yield renderScriptBlock(request, "settings.mako", "changePasswd",
                                    landing, "#settings-content", "set", **args)
        else:
            newPasswd = utils.md5(passwd1)
            yield db.insert(emailId, "userAuth", newPasswd, "passwordHash")
            args["successMsg"] = "Password changed."
            yield renderScriptBlock(request, "settings.mako", "changePasswd",
                                    landing, "#settings-content", "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _edit(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        userInfo = {}
        calls = []

        for cn in ("jobTitle", "location", "desc", "name", "firstname", "lastname", "timezone"):
            val = utils.getRequestArg(request, cn)
            if val:
                userInfo.setdefault("basic", {})[cn] = val

        user = yield db.get_slice(myKey, "entities", ["basic"])
        user = utils.supercolumnsToDict(user)

        cols = yield db.get_slice(myKey, 'connections', )
        friends = [item.super_column.name for item in cols] + [args["orgKey"]]

        for field in ["name", "lastname", "firstname"]:
            if "basic" in userInfo and field in userInfo["basic"]:
                d = utils.updateNameIndex(myKey, friends,
                                          userInfo["basic"][field],
                                          user["basic"].get(field, None))
                if field == 'name':
                    d1 = utils.updateDisplayNameIndex(myKey, friends,
                                                userInfo["basic"][field],
                                                user["basic"].get(field, None))
                    calls.append(d1)
                calls.append(d)

        if calls:
            yield defer.DeferredList(calls)

        if "basic" in userInfo:
            basic_acl = utils.getRequestArg(request, "basic_acl") or 'public'
            userInfo["basic"]["acl"] = basic_acl

        dp = utils.getRequestArg(request, "dp", sanitize=False)
        if dp:
            avatar = yield saveAvatarItem(myKey, dp)
            if not userInfo.has_key("basic"):
                userInfo["basic"] = {}
            userInfo["basic"]["avatar"] = avatar

        expertise = utils.getRequestArg(request, "expertise")
        expertise_acl = utils.getRequestArg(request, "expertise_acl") or 'public'
        if expertise:
            userInfo["expertise"] = {}
            userInfo["expertise"][expertise]=""
            userInfo["expertise"]["acl"]=expertise_acl

        language = utils.getRequestArg(request, "language")
        lr = utils.getRequestArg(request, "language_r") == "on"
        ls = utils.getRequestArg(request, "language_s") == "on"
        lw = utils.getRequestArg(request, "language_w") == "on"
        language_acl = utils.getRequestArg(request, "language_acl") or 'public'
        if language:
            userInfo["languages"]= {}
            userInfo["languages"][language]= "%(lr)s/%(lw)s/%(ls)s" %(locals())
            userInfo["languages"]["acl"] = language_acl

        c_email = utils.getRequestArg(request, "c_email")
        c_im = utils.getRequestArg(request, "c_im")
        c_phone = utils.getRequestArg(request, "c_phone")
        c_mobile = utils.getRequestArg(request, "c_mobile")
        contacts_acl = utils.getRequestArg(request, "contacts_acl") or 'public'

        if any([c_email, c_im, c_phone]):
            userInfo["contact"] = {}
            userInfo["contact"]["acl"] = contacts_acl

        if c_email:
            userInfo["contact"]["mail"] = c_email
        if c_im:
            userInfo["contact"]["im"] = c_im
        if c_phone:
            userInfo["contact"]["phone"] = c_phone
        if c_mobile:
            userInfo["contact"]["mobile"] = c_mobile

        interests = utils.getRequestArg(request, "interests")
        interests_acl = utils.getRequestArg(request, "interests_acl") or 'public'
        if interests:
            userInfo["interests"]= {}
            userInfo["interests"][interests]= interests
            userInfo["interests"]["acl"] = interests_acl

        p_email = utils.getRequestArg(request, "p_email")
        p_phone = utils.getRequestArg(request, "p_phone")
        p_mobile = utils.getRequestArg(request, "p_mobile")
        currentCity = utils.getRequestArg(request, "currentCity")
        dob_day = utils.getRequestArg(request, "dob_day")
        dob_mon = utils.getRequestArg(request, "dob_mon")
        dob_year = utils.getRequestArg(request, "dob_year")
        hometown = utils.getRequestArg(request, "hometown")
        currentCity = utils.getRequestArg(request, "currentCity")
        personal_acl = utils.getRequestArg(request, "personal_acl") or 'public'
        if any([p_email, p_phone, hometown, currentCity,]) \
            or all([dob_year, dob_mon, dob_day]):
            userInfo["personal"]={}
        if p_email:
            userInfo["personal"]["email"] = p_email
        if p_phone:
            userInfo["personal"]["phone"] = p_phone
        if p_mobile:
            userInfo["personal"]["mobile"] = p_mobile
        if hometown:
            userInfo["personal"]["hometown"] = hometown
        if currentCity:
            userInfo["personal"]["currentCity"] = currentCity
        if dob_day and dob_mon and dob_year:
            if dob_day.isdigit() and dob_mon.isdigit() and dob_year.isdigit():
                if int(dob_day) in range(1, 31) and \
                    int(dob_mon) in range(1, 12) and \
                        int(dob_year) in range(1901, 2099):
                    if int(dob_mon) < 10:
                        dob_mon = "%02d" %int(dob_mon)
                    userInfo["personal"]["birthday"] = "%s%s%s"%(dob_year, dob_mon, dob_day)

        employer = utils.getRequestArg(request, "employer")
        emp_start = utils.getRequestArg(request, "emp_start") or ''
        emp_end = utils.getRequestArg(request, "emp_end") or ''
        emp_title = utils.getRequestArg(request, "emp_title") or ''
        emp_desc = utils.getRequestArg(request, "emp_desc") or ''

        if employer:
            userInfo["employers"] = {}
            key = "%s:%s:%s:%s" %(emp_end, emp_start, employer, emp_title)
            userInfo["employers"][key] = emp_desc

        college = utils.getRequestArg(request, "college")
        degree = utils.getRequestArg(request, "degree") or ''
        edu_end = utils.getRequestArg(request, "edu_end") or ''
        if college:
            userInfo["education"] = {}
            key = "%s:%s" %(edu_end, college)
            userInfo["education"][key] = degree

        if userInfo:
            yield db.batch_insert(myKey, "entities", userInfo)

        if not self._ajax:
            request.redirect("/settings")
        else:
            pass
            #TODO: If basic profile was edited, then logo, name and title could
            # also change, make sure these are reflected too.


    @defer.inlineCallbacks
    def _updateNotifications(self, request):

        """
            someone sends friend request
            someone accepts friend request
            group request is accepted.
            someone invites me to a group
            some one is following me
            someone likes/likes-comment/comments on my post
            someone commented/liked my comment on others post
            someone mentions me in a post/comment
        """

        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        intify = lambda x: int(x or 0)
        log.msg(request.args)

        new_friend_request = intify(utils.getRequestArg(request, 'new_friend_request'))
        accepted_my_friend_request = intify(utils.getRequestArg(request, 'accepted_my_friend_request'))
        new_follower = intify(utils.getRequestArg(request, 'new_follower'))
        new_member_to_network = intify(utils.getRequestArg(request, 'new_member_to_network'))

        new_group_invite = intify(utils.getRequestArg(request, 'new_group_invite'))
        pending_group_request = intify(utils.getRequestArg(request, "pending_group_request")) # admin only
        accepted_my_group_membership = intify(utils.getRequestArg(request, 'accepted_my_group_membership'))
        new_post_to_group = intify(utils.getRequestArg(request, 'new_post_to_group'))

        new_message = intify(utils.getRequestArg(request, 'new_message'))
        #new_message_reply = intify(utils.getRequestArg(request, 'new_message_reply'))

        others_act_on_my_post = intify(utils.getRequestArg(request, 'others_act_on_my_post'))
        others_act_on_item_following = intify(utils.getRequestArg(request, 'others_act_on_item_following'))

        #mention_in_post = intify(utils.getRequestArg(request, 'mention_in_post'))

        count = 0
        count |= new_friend_request
        count |= accepted_my_friend_request<<1
        count |= new_follower<<2
        count |= new_member_to_network<<3

        count |= new_group_invite<<4
        count |= pending_group_request<<5
        count |= accepted_my_group_membership<<6
        count |= new_post_to_group<<7

        count |= new_message<<8
        #count |= new_message_reply<<9

        count |= others_act_on_my_post <<10
        count |= others_act_on_item_following<<11

        yield db.insert(myId, 'entities', str(count), 'email_preferences', 'basic')


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        detail = utils.getRequestArg(request, "dt") or "basic"
        args["detail"] = detail
        args["editProfile"] = True

        if script and landing:
            yield render(request, "settings.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        handlers={"onload": "$$.menu.selectItem('%s');"%detail }
        if detail == "basic":
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            handlers["onload"] += """$$.ui.bindFormSubmit('#profile_form');"""
            yield renderScriptBlock(request, "settings.mako", "editBasicInfo",
                                    landing, "#settings-content", "set", True,
                                    handlers = handlers, **args)

        elif detail == "work":
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            yield renderScriptBlock(request, "settings.mako", "editWork",
                                    landing, "#settings-content", "set", True,
                                    handlers=handlers, **args)

        elif detail == "personal":
            res = yield db.get_slice(myKey, "entities", ['personal'])
            personalInfo = utils.supercolumnsToDict(res).get("personal", {})
            args.update({"personalInfo":personalInfo})
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            yield renderScriptBlock(request, "settings.mako", "editPersonal",
                                    landing, "#settings-content", "set", True,
                                    handlers=handlers, **args)

        elif detail == "contact":
            res = yield db.get_slice(myKey, "entities", ['contact'])
            contactInfo = utils.supercolumnsToDict(res).get("contact", {})
            args.update({"contactInfo":contactInfo})
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            yield renderScriptBlock(request, "settings.mako", "editContact",
                                    landing, "#settings-content", "set",True,
                                    handlers=handlers, **args)

        elif detail == "passwd":
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            yield renderScriptBlock(request, "settings.mako", "changePasswd",
                                    landing, "#settings-content", "set",True,
                                    handlers=handlers, **args)

        elif detail == 'notify':
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)
            yield renderScriptBlock(request, "settings.mako", "emailPreferences",
                                    landing, "#settings-content", "set",True,
                                    handlers=handlers, **args)


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._edit(request)
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == "passwd":
                d = self._changePassword(request)
            elif action == "notify":
                d = self._updateNotifications(request)

        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)

        return self._epilogue(request, d)
