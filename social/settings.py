import PythonMagick
import imghdr
import time
import uuid
from random                 import sample
import datetime
import json

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


#############################################################
# XXX: Don't change values assigned to notification types   #
#      If you do, existing preferences will break.          #
#############################################################

notifyFriendRequest = 0
notifyFriendAccept = 1
notifyNewFollower = 2
notifyNewOrgUser = 3

notifyGroupRequest = 4
notifyGroupAccept = 5
notifyGroupInvite = 6
notifyGroupNewMember = 7

notifyMyItemT = 8
notifyMyItemC = 9
notifyMyItemL = 10
notifyMyItemLC = notifyItemLC = 11
notifyItemC = 12

notifyMention = 13
notifyItemRequests = 14

notifyMessageConv = 15
notifyMessageMessage = 16
notifyMessageAccessChange = 17

# Total number of notification types and default setting
_notificationsCount = 18
defaultNotify = "3" * _notificationsCount

# Notification medium
notifyByMail = 1
notifyBySMS = 2

# Names of each notification type (by index as given above)
_notifyNames = ['friendRequest', 'friendAccept', 'follower', 'newMember',
    'groupRequest', 'groupAccept', 'groupInvite', 'groupNewMember',
    'myItemTag', 'myItemComment', 'myItemlike', 'itemCommentLike',
    'itemComment', 'mention', 'itemRequests',
    'messageConv', 'messageMessage', 'messageAccessChange']
    
# Utility function to help parse the notification preference
# In case of an exception returns true
def getNotifyPref(val, typ, medium):
    try:
        if not int(val[typ]) & medium:
            return False
    except IndexError,ValueError: pass
    return True


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

        if not curr_passwd:
            request.write('$$.alerts.error("%s");' % _("Enter your current password"))
            defer.returnValue(None)
        if not passwd1:
            request.write('$$.alerts.error("%s");' % _("Enter new password"))
            defer.returnValue(None)
        if not passwd2:
            request.write('$$.alerts.error("%s");' % _("Confirm new password"))
            defer.returnValue(None)
        if passwd1 != passwd2:
            request.write('$$.alerts.error("%s");' % _("Passwords do not match"))
            defer.returnValue(None)
        if curr_passwd == passwd1:
            request.write('$$.alerts.error("%s");' % _("New password should be different from current password"))
            defer.returnValue(None)

        cols = yield db.get(myKey, "entities", "emailId", "basic")
        emailId = cols.column.value
        col = yield db.get(emailId, "userAuth", "passwordHash")
        passwdHash = col.column.value
        if curr_passwd and passwdHash != utils.md5(curr_passwd):
            request.write('$$.alerts.error("%s");' % _("Incorrect Password"))
            defer.returnValue(None)

        newPasswd = utils.md5(passwd1)
        yield db.insert(emailId, "userAuth", newPasswd, "passwordHash")
        request.write('$$.alerts.info("%s");' % _('Password changed'))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _edit(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        userInfo = {}
        calls = []
        basicUpdatedInfo = {}

        me = yield db.get_slice(myKey, 'entities')
        me = utils.supercolumnsToDict(me)

        cols = yield db.get_slice(myKey, 'connections')
        friends = [item.super_column.name for item in cols]

        # Check if any basic information is being updated.
        for cn in ("jobTitle", "location", "desc", "name", "firstname", "lastname", "timezone"):
            val = utils.getRequestArg(request, cn)
            if val:
                userInfo.setdefault("basic", {})[cn] = val
                basicUpdatedInfo[cn] = val
            else:
                basicUpdatedInfo[cn] = me['basic'].get(cn, "")
                
        # Update name indicies of organization and friends.
        nameIndexKeys = friends + [args["orgKey"]]
        nameIndicesDeferreds = []
        for field in ["name", "lastname", "firstname"]:
            if "basic" in userInfo and field in userInfo["basic"]:
                d = utils.updateNameIndex(myKey, nameIndexKeys,
                                          userInfo["basic"][field],
                                          me["basic"].get(field, None))
                if field == 'name':
                    d1 = utils.updateDisplayNameIndex(myKey, nameIndexKeys,
                                                userInfo["basic"][field],
                                                me["basic"].get(field, None))
                    nameIndicesDeferreds.append(d1)
                nameIndicesDeferreds.append(d)

        # ACL on basic information
        basicACL = utils.getRequestArg(request, "basicACL") or\
                                            me['basic'].get('acl', 'public')
        userInfo.setdefault("basic", {})["acl"] = basicACL

        # Avatar (display picture)
        dp = utils.getRequestArg(request, "dp", sanitize=False)
        if dp:
            avatar = yield saveAvatarItem(myKey, dp)
            if not userInfo.has_key("basic"):
                userInfo["basic"] = {}
            userInfo["basic"]["avatar"] = avatar
            avatarURI = utils.userAvatar(myKey, userInfo)
            basicUpdatedInfo["avatar"] = avatarURI

        # Contact information at work.
        c_im = utils.getRequestArg(request, "c_im")
        c_phone = utils.getRequestArg(request, "c_phone")
        c_mobile = utils.getRequestArg(request, "c_mobile")

        if any([c_mobile, c_im, c_phone]):
            contactsACL = utils.getRequestArg(request, "contactsACL") or\
                                me.get('contact', {}).get('acl', 'public')
            userInfo["contact"] = {}
            userInfo["contact"]["acl"] = contactsACL
        if c_im:
            userInfo["contact"]["im"] = c_im
        if c_phone:
            userInfo["contact"]["phone"] = c_phone
        if c_mobile:
            userInfo["contact"]["mobile"] = c_mobile

        # Personal information about the user
        p_email = utils.getRequestArg(request, "p_email")
        p_phone = utils.getRequestArg(request, "p_phone")
        p_mobile = utils.getRequestArg(request, "p_mobile")
        currentCity = utils.getRequestArg(request, "currentCity")
        dob_day = utils.getRequestArg(request, "dob_day") or None
        dob_mon = utils.getRequestArg(request, "dob_mon") or None
        dob_year = utils.getRequestArg(request, "dob_year") or None
        hometown = utils.getRequestArg(request, "hometown")

        validDate = False
        try:
            dateStr = "%s/%s/%s" % (dob_day, dob_mon, dob_year)
            date = time.strptime(dateStr, "%d/%m/%Y")
            if date.tm_year < time.localtime().tm_year:
                dob_day = "%02d" % date.tm_mday
                dob_mon = "%02d" % date.tm_mon
                validDate = True
        except ValueError:
            pass

        if any([p_email, p_phone, hometown, currentCity, validDate]):
            personalACL = utils.getRequestArg(request, "personalACL") or\
                                    me.get('personal', {}).get('acl', 'public')
            userInfo["personal"]={"acl": personalACL}

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
        if validDate:
            userInfo["personal"]["birthday"] = "%s%s%s" % (dob_year, dob_mon, dob_day)

        # If anything was modified save it.
        if userInfo:
            yield db.batch_insert(myKey, "entities", userInfo)

        if not self._ajax:
            request.redirect("/settings")
        else:
            if len(basicUpdatedInfo.keys()) > 0:
                response = """
                            <script>
                                var data = %s;
                                if (data.avatar){
                                  var imageUrl = data.avatar;
                                  parent.$('#avatar').css('background-image', 'url(' + imageUrl + ')');
                                }
                                parent.$('#name').html(data.name + ', ' + data.jobTitle);
                                parent.$$.alerts.info("%s");
                            </script>
                           """ % (json.dumps(basicUpdatedInfo),  _("Profile updated"))
                request.write(response)
            else:
                request.write('$$.alerts.info("%s");' % _('Profile updated'))

        # Wait for name indices to be updated.
        if nameIndicesDeferreds:
            yield defer.DeferredList(nameIndicesDeferreds)

        args["detail"] = ""
        suggestedSections = yield self._checkProfileCompleteness(request, myKey, args)
        tmp_suggested_sections = {}
        for section, items in suggestedSections.iteritems():
            if len(suggestedSections[section]) > 0:
                tmp_suggested_sections[section] = items
        args.update({'suggested_sections':tmp_suggested_sections})

        yield renderScriptBlock(request, "settings.mako", "right",
                                landing, ".right-contents", "set", **args)

    @defer.inlineCallbacks
    def _updateNotifications(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        getArg = utils.getRequestArg
        def _get(typ):
            val = getArg(request, typ)
            try:
                return val if (0 < int(val) <= 3) else '0'
            except (ValueError,TypeError):
                return '0'

        prefVal = ''.join([_get(x) for x in _notifyNames])
        yield db.insert(myId, 'entities', prefVal, 'notify', 'basic')
        request.write('$$.alerts.info("%s");' % _('Preferences saved'))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        detail = utils.getRequestArg(request, "dt") or "basic"
        args["detail"] = detail
        args["editProfile"] = True

        me = yield db.get_slice(myKey, "entities")
        args["me"] = utils.supercolumnsToDict(me, ordered=True)

        if script and landing:
            yield render(request, "settings.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            handlers={"onload": "$$.menu.selectItem('%s');" % detail}
            if detail == "basic":
                yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                        landing, "#settings-title", "set", **args)
                handlers["onload"] += """$$.ui.bindFormSubmit('#settings-form');"""
                yield renderScriptBlock(request, "settings.mako", "editBasicInfo",
                                        landing, "#settings-content", "set", True,
                                        handlers = handlers, **args)

            elif detail == "work":
                """
                yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                        landing, "#settings-title", "set", **args)
                yield renderScriptBlock(request, "settings.mako", "editWork",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)
                """

            elif detail == "personal":
                yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                        landing, "#settings-title", "set", **args)
                yield renderScriptBlock(request, "settings.mako", "editPersonal",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)

            elif detail == "contact":
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
                yield renderScriptBlock(request, "settings.mako", "filterNotifications",
                                        landing, "#settings-content", "set",True,
                                        handlers=handlers, **args)

        suggestedSections = yield self._checkProfileCompleteness(request, myKey, args)
        tmp_suggested_sections = {}
        for section, items in suggestedSections.iteritems():
            if len(suggestedSections[section]) > 0:
                tmp_suggested_sections[section] = items
        args.update({'suggested_sections':tmp_suggested_sections})
        if script:
            yield renderScriptBlock(request, "settings.mako", "right",
                                    landing, ".right-contents", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "settings.mako", **args)


    """
    def _validateYear(self, year, name):
        try:
            curr = time.localtime()
            if not 1900 < int(year) <= curr.tm_year:
                return None
        except ValueError:
            return None
        return year

    @defer.inlineCallbacks
    def _deleteEmployer(self, request):
        encodedId = utils.getRequestArg(request, 'id')
        empId = utils.decodeKey(encodedId)
        yield db.remove(myId, "entities", empId, "employers")
        request.write('$("#emp-%s").remove();' % empId)


    @defer.inlineCallbacks
    def _updateEmployer(self, request):
        encodedId = utils.getRequestArg(request, 'id') or None
        if encodedId:
            empId = utils.decodeKey(encodedId)
            yield db.remove(myId, "entities", empId, "employers")

        company = utils.getRequestArg(request, 'company')
        desc = utils.getRequestArg(request, 'desc') or ''
        start = utils.getRequestArg(request, 'start') or ''
        end = utils.getRequestArg(request, 'end') or ''

        start = self._validateYear(start, "Start")
        end = self._validateYear(end, "End")

        if not (start or company):
            raise errors.MissingParams(_(['Start Year', 'Company Name']))

        newEmpId = "%s:%s:%s" % (end, start, company)
        yield db.insert(myId, "entities", desc, newEmpId, "employers")

        yield renderScriptBlock(request, "settings.mako", "employer",
                                landing, "#emplist", "append",
                                args=[start, end, company, desc])


    @defer.inlineCallbacks
    def _deleteWork(self, request):
        encodedId = utils.getRequestArg(request, 'id')
        workId = utils.decodeKey(encodedId)
        yield db.remove(myId, "entities", workId, "work")
        request.write('$("#work-%s").remove();' % workId)


    @defer.inlineCallbacks
    def _editWorkForm(self, request):
        encodedId = utils.getRequestArg(request, 'id')
        end, start, title, desc = None, None, None, None
        if encodedId:
            workId = utils.decodeKey(encodedId)
            try:
                col = yield db.get(myId, "entities", workId, "work")
                end, start, title = workId.split(':')
                desc = col.column.value
            except ttypes.NotFoundException:
                workId = None

            yield renderScriptBlock(request, "settings.mako", "workForm",
                                    False, "#"+workId, "replace",
                                    args=[start, end, company, desc, encodedId])
        else:
            yield renderScriptBlock(request, "settings.mako", "workForm",
                                    False, "#workadd", "replace")


    @defer.inlineCallbacks
    def _updateWork(self, request):
        myId = request.getSession(IAuthInfo).username
        encodedId = utils.getRequestArg(request, 'id') or None
        if encodedId:
            workId = utils.decodeKey(encodedId)
            yield db.remove(myId, "entities", workId, "work")

        title = utils.getRequestArg(request, 'title')
        desc = utils.getRequestArg(request, 'desc') or ''
        start = utils.getRequestArg(request, 'start') or ''
        end = utils.getRequestArg(request, 'end') or ''

        start = self._validateYear(start, "Start")
        end = self._validateYear(end, "End")

        if not (start or title):
            raise errors.MissingParams(_(['Start Year', 'Title']))

        newWorkId = "%s:%s:%s" % (end, start, title)
        yield db.insert(myId, "entities", desc, newWorkId, "work")

        if not encodedId:
            yield renderScriptBlock(request, "settings.mako", "workitem",
                                    False, "#worklist", "append",
                                    args=[start, end, title, desc])
            yield renderScriptBlock(request, "settings.mako", "workAddButton",
                                    False, "#workform", "replace")
        else:
            yield renderScriptBlock(request, "settings.mako", "workitem",
                                    False, "#work-"+workId, "replace",
                                    args=[start, end, title, desc])


    @defer.inlineCallbacks
    def _deleteEducation(self, request):
        encodedId = utils.getRequestArg(request, 'id')
        eduId = utils.decodeKey(encodedId)
        yield db.remove(myId, "entities", eduId, "education")
        request.write('$("#edu-%s").remove();' % eduId)


    @defer.inlineCallbacks
    def _updateEducation(self, request):
        encodedId = utils.getRequestArg(request, 'id') or None
        if encodedId:
            eduId = utils.decodeKey(encodedId)
            yield db.remove(myId, "entities", eduId, "education")

        college = utils.getRequestArg(request, 'college')
        course = utils.getRequestArg(request, 'course')
        year = utils.getRequestArg(request, 'year') or ''
        year = self._validateYear(year, "Graduation Year")

        if not (year or college or course):
            raise errors.MissingParams(_(['Year of graduation', 'College', 'Course']))

        newEduId = "%s:%s:%s" % (year, college, course)
        yield db.insert(myId, "entities", "", newEduId, "education")

        yield renderScriptBlock(request, "settings.mako", "education",
                                landing, "#edulist", "append",
                                args=[year, college, course])
    """

    @defer.inlineCallbacks
    def _checkProfileCompleteness(self, request, myKey, args):
        landing = not self._ajax
        description = [""]
        detail = args["detail"]

        if detail == "basic":
            description = ["""Your Basic details are the most discoverable
                            fields in your profile. They are visible everytime
                            someone searches for you. We recommend that you fill
                            out all the fields in this section.
                          """]

        elif detail == "work":
            description = ["""Your work details include your current and
                             previous work experiences and also about your
                             educational background. """,
                           """A thorough work experience builds up a nice
                             portfolio of your career."""]

        elif detail == "personal":
            description = ["""Your personal information is only accessible to your
                             friends.
                          """]

        elif detail == "contact":
            description = ["""Your contact information can be used to get in
                             touch with you by your friends or your followers.
                             We recommend completing this section if your work
                             involves being in constant touch with your colleagues.
                          """]

        elif detail == "passwd":
            description = ["""Change your password. Use a password consisting of
                             atleast 8 characters including alphabets, numbers
                             and special characters.
                          """]

        elif detail == 'notify':
            description = ["""flockedIn can notify you of all the activities that
                             were happening in your
                             <i title="kol-eeg-o-sfeer">colleagosphere</i>
                             while you were
                             away.""",
                           """ Here you can choose what kind of events
                             you like to be notified of."""]

        args["description"] = description

        suggestedSections = {}

        # Check Basic
        requiredFields = ["jobTitle", "timezone"]
        jobTitle = args["me"].get("basic", {}).get("jobTitle", None)
        myTimezone = args["me"].get("basic", {}).get("timezone", None)
        suggestedSections["basic"] = []
        if jobTitle is None:
            suggestedSections["basic"].append("Add a job title")
        if myTimezone is None:
            suggestedSections["basic"].append("Configure your timezone")

        # Check Contact
        suggestedSections["contact"] = []
        if "contactInfo" not in args:
            res = yield db.get_slice(myKey, "entities", ['contact'])
            contactInfo = utils.supercolumnsToDict(res).get("contact", {})
        else:
            contactInfo = args["contactInfo"]

        phone = contactInfo.get('phone', None)
        if not phone:
            suggestedSections["contact"].append("Add a work phone")

        # Check Personal Info
        suggestedSections["personal"] = []
        if "personalInfo" not in args:
            res = yield db.get_slice(myKey, "entities", ['personal'])
            personalInfo = utils.supercolumnsToDict(res).get("personal", {})
        else:
            personalInfo = args["personalInfo"]

        currentCity = personalInfo.get('currentCity', None)
        if not currentCity:
            suggestedSections["personal"].append("Which city are you residing in")

        # Check Work
        #suggestedSections["work"] = []
        #if "workInfo" not in args:
        #    res = yield db.get_slice(myKey, "entities", ['work', 'employers', 'education'])
        #    currentWorkInfo = utils.supercolumnsToDict(res).get("work", {})
        #    previousWorkInfo = utils.supercolumnsToDict(res).get("employers", {})
        #    educationInfo = utils.supercolumnsToDict(res).get("education", {})
        #else:
        #    currentWorkInfo = args["currentWorkInfo"]
        #    previousWorkInfo = args["previousWorkInfo"]
        #    educationInfo = args["educationInfo"]
        #
        #if len(currentWorkInfo.keys()) == 0:
        #    suggestedSections["work"].append("Write about your current work")
        #
        #if len(previousWorkInfo.keys()) == 0 and len(educationInfo.keys()) == 0:
        #    suggestedSections["work"].append("Write something about your previous work")
        #    suggestedSections["work"].append("Write about your academics")

        #if len(educationInfo.keys()) == 0:
        #    suggestedSections["work"].append("Write about your academics")

        #academic_durations = [int(x.split(':')[0]) for x in educationInfo.keys()]
        #last_passed = sorted(academic_durations)[-1]
        #if (datetime.date.today().year - last_passed > 2) and \
        #    (len(previousWorkInfo.keys()) == 0):
        #    suggestedSections["work"].append("Write about your previous work")

        defer.returnValue(suggestedSections)


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
            """
            elif action == "work":
                d = self._updateWork(request)
            """

        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)
        """
        elif segmentCount == 1:
            action = request.postpath[0]
            if action == "work":
                d = self._editWorkForm(request)
        """

        return self._epilogue(request, d)
