import PythonMagick
import imghdr
import time
import uuid
from random                 import sample
import datetime
import json
import re
from base64                 import b64encode, b64decode

from twisted.web            import resource, server, http
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef, renderScriptBlock
from social.relations       import Relation
from social                 import db, utils, base, plugins, _, __, fts
from social                 import constants, feed, errors
from social.logging         import dump_args, profile, log
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

notifyFR = 0
notifyFA = 1
notifyNF = 2
notifyNU = 3
notifyIA = 3    # Invitation accept and invited user joining are same

notifyGR = 4
notifyGA = 5
notifyGI = 6
notifyGroupNewMember = 7

notifyMyItemT = 8
notifyMyItemC = 9
notifyMyItemL = 10
notifyMyItemLC = notifyItemLC = 11
notifyItemC = 12

notifyMention = 13
notifyItemRequests = 14

notifyNM = 15
notifyMR = 16
notifyMA = 17

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

# List of notifications that currently must not be displayed to the user
_hiddenNotifys = [notifyFR, notifyFA, notifyMention, notifyItemRequests]

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
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        currentPass = utils.getRequestArg(request, "curr_passwd", sanitize=False)
        newPass = utils.getRequestArg(request, "passwd1", sanitize=False)
        rptPass = utils.getRequestArg(request, "passwd2", sanitize=False)

        if not currentPass:
            request.write('$$.alerts.error("%s");' % _("Enter your current password"))
            defer.returnValue(None)
        if not newPass:
            request.write('$$.alerts.error("%s");' % _("Enter new password"))
            defer.returnValue(None)
        if not rptPass:
            request.write('$$.alerts.error("%s");' % _("Confirm new password"))
            defer.returnValue(None)
        if newPass != rptPass:
            request.write('$$.alerts.error("%s");' % _("Passwords do not match"))
            defer.returnValue(None)
        if currentPass == newPass:
            request.write('$$.alerts.error("%s");' % _("New password should be different from current password"))
            defer.returnValue(None)

        emailId = args["me"]["basic"]["emailId"]
        col = yield db.get(emailId, "userAuth", "passwordHash")
        storedPass= col.column.value

        if not utils.checkpass(currentPass, storedPass):
            request.write('$$.alerts.error("%s");' % _("Incorrect Password"))
            defer.returnValue(None)

        newPasswd = utils.hashpass(newPass)
        yield db.insert(emailId, "userAuth", newPasswd, "passwordHash")
        request.write('$$.alerts.info("%s");' % _('Password changed'))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _editPersonalInfo(self, request):
        # Personal information about the user
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        landing = False
        data = {}
        to_remove = []

        me = yield db.get_slice(myId, 'entities')
        me = utils.supercolumnsToDict(me)
        dob_day = utils.getRequestArg(request, "dob_day") or None
        dob_mon = utils.getRequestArg(request, "dob_mon") or None
        dob_year = utils.getRequestArg(request, "dob_year") or None

        if dob_day and dob_mon and dob_year:
            try:
                dateStr = "%s/%s/%s" % (dob_day, dob_mon, dob_year)
                date = time.strptime(dateStr, "%d/%m/%Y")
                if date.tm_year < time.localtime().tm_year:
                    dob_day = "%02d" % date.tm_mday
                    dob_mon = "%02d" % date.tm_mon
                    data["birthday"] = "%s%s%s" % (dob_year, dob_mon, dob_day)
            except ValueError:
                raise errors.InvalidRequest(_('Please select a valid Date of Birth'))
        else:
            to_remove.append('birthday')

        columnNames = ['email', 'phone', 'mobile', 'hometown', 'currentCity']
        for name in columnNames:
            val = utils.getRequestArg(request, name)

            if val:
                data[name] = val
            else:
                to_remove.append(name)
        if data:
            yield db.batch_insert(myId, "entities", {"personal": data})
        if to_remove:
            yield db.batch_remove({'entities':[myId]}, names=to_remove, supercolumn='personal')

        if 'phone' in data and not re.match('^\+?[0-9x\- ]{5,20}$', data['phone']):
            raise errors.InvalidRequest(_('Phone numbers can only have numerals, hyphens, spaces and a plus sign'))

        if 'mobile' in data and not re.match('^\+?[0-9x\- ]{5,20}$', data['mobile']):
            raise errors.InvalidRequest(_('Phone numbers can only have numerals, hyphens, spaces and a plus sign'))

        columnNames.append('birthday')
        personalInfo =  me.get('personal', {})
        if any([personalInfo.get(x, None) != data.get(x, None) for x in columnNames]):
            request.write('$$.alerts.info("%s");' % _('Profile updated'))

        args = {"detail": "", "me": me}
        suggestedSections = yield self._checkProfileCompleteness(request, myId, args)
        tmp_suggested_sections = {}
        for section, items in suggestedSections.iteritems():
            if len(suggestedSections[section]) > 0:
                tmp_suggested_sections[section] = items
        args.update({'suggested_sections':tmp_suggested_sections})

        yield renderScriptBlock(request, "settings.mako", "right",
                                landing, ".right-contents", "set", **args)
        me.update({'personal':data})
        yield fts.solr.updatePeopleIndex(myId, me, orgId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _editWorkInfo(self, request):
        # Contact information at work.
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        landing = not self._ajax

        me = yield db.get_slice(myId, 'entities')
        me = utils.supercolumnsToDict(me)
        data = {}
        to_remove = []

        for field in ["im", "phone", "mobile"]:
            val = utils.getRequestArg(request, field)
            if val:
                data[field] = val
            else:
                to_remove.append(field)

        if 'phone' in data and not re.match('^\+?[0-9x\- ]{5,20}$', data['phone']):
            raise errors.InvalidRequest(_('Phone numbers can only have numerals, hyphens, spaces and a plus sign'))

        if 'mobile' in data and not re.match('^\+?[0-9x\- ]{5,20}$', data['mobile']):
            raise errors.InvalidRequest(_('Phone numbers can only have numerals, hyphens, spaces and a plus sign'))

        if data:
            yield db.batch_insert(myId, "entities", {"contact": data})
        if to_remove:
            yield db.batch_remove({"entities":[myId]}, names= to_remove, supercolumn='contact')
        contactInfo = me.get('contact', {})
        if any([contactInfo.get(x, None) != data.get(x, None) for x in ["im", "phone", "mobile"]]):
            request.write('$$.alerts.info("%s");' % _('Profile updated'))

        args = {"detail": "", "me": me}
        suggestedSections = yield self._checkProfileCompleteness(request, myId, args)
        tmp_suggested_sections = {}
        for section, items in suggestedSections.iteritems():
            if len(suggestedSections[section]) > 0:
                tmp_suggested_sections[section] = items
        args.update({'suggested_sections':tmp_suggested_sections})

        yield renderScriptBlock(request, "settings.mako", "right",
                                landing, ".right-contents", "set", **args)
        me.update({'contact':data})
        yield fts.solr.updatePeopleIndex(myId, me, orgId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _editBasicInfo(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        landing = not self._ajax

        userInfo = {"basic":{}}
        to_remove = []
        basicUpdatedInfo, basicUpdated = {}, False

        me = yield db.get_slice(myId, 'entities')
        me = utils.supercolumnsToDict(me)

        # Check if any basic information is being updated.
        for cn in ("jobTitle", "name", "firstname", "lastname", "timezone"):
            val = utils.getRequestArg(request, cn)
            if not val and cn in ['name', 'jobTitle', 'timezone']:
                request.write("<script>parent.$$.alerts.error('One or more required parameters are missing')</script>")
                raise errors.MissingParams(_([cn]))
            if val:
                userInfo["basic"][cn] = val
                basicUpdatedInfo[cn] = val
            elif cn in ["firstname", "lastname"]:
                to_remove.append(cn)
                basicUpdatedInfo[cn] = ""
            if me['basic'].get(cn, None) != userInfo['basic'].get(cn, None):
                basicUpdated = True

        # Update name indicies of organization.
        nameIndexKeys = [orgId]
        nameIndicesDeferreds = []
        oldNameParts = []
        newNameParts = []
        for field in ["name", "lastname", "firstname"]:
            if field in basicUpdatedInfo:
                newNameParts.extend(basicUpdatedInfo[field].split())
                oldNameParts.extend(me['basic'].get(field, '').split())
                if field == 'name':
                    d1 = utils.updateDisplayNameIndex(myId, nameIndexKeys,
                                                      basicUpdatedInfo[field],
                                                      me["basic"].get(field, None))
                    nameIndicesDeferreds.append(d1)
        d = utils.updateNameIndex(myId, nameIndexKeys,
                                  " ".join(newNameParts),
                                  " ".join(oldNameParts))
        nameIndicesDeferreds.append(d)

        # Avatar (display picture)
        dp = utils.getRequestArg(request, "dp", sanitize=False)
        if dp:
            avatar = yield saveAvatarItem(myId, dp)
            userInfo["basic"]["avatar"] = avatar
            avatarURI = utils.userAvatar(myId, userInfo)
            basicUpdatedInfo["avatar"] = avatarURI
            basicUpdated = True
        if userInfo["basic"]:
            yield db.batch_insert(myId, "entities", userInfo)
            me.update(userInfo)
            yield fts.solr.updatePeopleIndex(myId, me, orgId)

        if to_remove:
            yield db.batch_remove({'entities':[myId]}, names=to_remove, supercolumn='basic')

        if basicUpdated:
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

        # Wait for name indices to be updated.
        if nameIndicesDeferreds:
            yield defer.DeferredList(nameIndicesDeferreds)

        args = {"detail": "", "me": me}
        suggestedSections = yield self._checkProfileCompleteness(request, myId, args)
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
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        detail = utils.getRequestArg(request, "dt") or "basic"
        args["detail"] = detail

        me = yield db.get_slice(myId, "entities")
        me = utils.supercolumnsToDict(me, ordered=True)
        args['me'] = me

        if script and landing:
            yield render(request, "settings.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "settings.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if script:
            yield renderScriptBlock(request, "settings.mako", "settingsTitle",
                                    landing, "#settings-title", "set", **args)

            handlers={"onload": "$$.menu.selectItem('%s');" % detail}
            if detail == "basic":
                handlers["onload"] += "$$.ui.bindFormSubmit('#settings-form');"
                yield renderScriptBlock(request, "settings.mako", "editBasicInfo",
                                        landing, "#settings-content", "set", True,
                                        handlers = handlers, **args)

            elif detail == "work":
                handlers["onload"] += """$('.expertise-input').tagedit({
                                            additionalListClass: 'styledform',
                                            breakKeyCodes: [13,44,32]
                                         });"""
                yield renderScriptBlock(request, "settings.mako", "editWork",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)

            elif detail == "personal":
                yield renderScriptBlock(request, "settings.mako", "editPersonal",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)

            elif detail == "passwd":
                yield renderScriptBlock(request, "settings.mako", "changePasswd",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)

            elif detail == "notify":
                yield renderScriptBlock(request, "settings.mako", "filterNotifications",
                                        landing, "#settings-content", "set", True,
                                        handlers=handlers, **args)

            else:
                raise errors.InvalidRequest('')

        suggestedSections = yield self._checkProfileCompleteness(request, myId, args)
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
    def _checkProfileCompleteness(self, request, myId, args):
        landing = not self._ajax
        detail = args["detail"]
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
            res = yield db.get_slice(myId, "entities", ['contact'])
            contactInfo = utils.supercolumnsToDict(res).get("contact", {})
        else:
            contactInfo = args["contactInfo"]

        phone = contactInfo.get('phone', None)
        if not phone:
            suggestedSections["contact"].append("Add a work phone")

        # Check Personal Info
        suggestedSections["personal"] = []
        if "personalInfo" not in args:
            res = yield db.get_slice(myId, "entities", ['personal'])
            personalInfo = utils.supercolumnsToDict(res).get("personal", {})
        else:
            personalInfo = args["personalInfo"]

        currentCity = personalInfo.get('currentCity', None)
        if not currentCity:
            suggestedSections["personal"].append("Which city are you residing in")

        # Check Work
        #suggestedSections["work"] = []
        #if "workInfo" not in args:
        #    res = yield db.get_slice(myId, "entities", ['work', 'employers', 'education'])
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


    @defer.inlineCallbacks
    def _editCompanyForm(self, request):
        encodedCompanyId = utils.getRequestArg(request, 'id')
        companyId = utils.decodeKey(encodedCompanyId) if encodedCompanyId else None

        if companyId:
            try:
                myId = request.getSession(IAuthInfo).username
                companyVal = yield db.get(myId, 'entities', companyId, "companies")
                companyVal = companyVal.column.value
                yield renderScriptBlock(request, "settings.mako", "companyForm",
                                        False, "#addemp-dlg", "set",
                                        args=[companyId, companyVal])
                return
            except: pass

        yield renderScriptBlock(request, "settings.mako", "companyForm",
                                False, "#addemp-dlg", "set")


    @defer.inlineCallbacks
    def _editCompany(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        remove = utils.getRequestArg(request, 'action') == 'd'
        encodedCompanyId = utils.getRequestArg(request, 'id', sanitize=False)
        companyId = utils.decodeKey(encodedCompanyId) if encodedCompanyId else None

        if companyId and remove:
            db.remove(myId, "entities", companyId, "companies")
            request.write('$("#%s").remove();' % encodedCompanyId)
            return

        curYear = datetime.date.today().year
        try:
            startYear = int(utils.getRequestArg(request, 'startyear'))
            if not 1900 < startYear <= curYear:
                raise ValueError
        except (ValueError,TypeError):
            raise errors.InvalidRequest('Invalid start year')

        try:
            endYear = utils.getRequestArg(request, 'endyear')
            if endYear == "present":
                endYear = 9999
            else:
                endYear = int(endYear)
                if not startYear <= endYear <= curYear:
                    raise ValueError
        except (ValueError,TypeError):
            raise errors.InvalidRequest('Invalid end year')

        name = utils.getRequestArg(request, 'company')
        title = utils.getRequestArg(request, 'title')

        if not remove and not name:
            errors.MissingParams(['Name'])

        if companyId:
            db.remove(myId, "entities", companyId, "companies")

        newCompanyId = "%s:%s:%s" % (endYear, startYear, name)
        newCompanyVal = title
        db.insert(myId, "entities", newCompanyVal, newCompanyId, "companies")

        request.write('$$.dialog.close("addemp-dlg");')
        if companyId:
            yield renderScriptBlock(request, "settings.mako", "companyItem",
                                    False, "#"+encodedCompanyId, "replace",
                                    args=[newCompanyId, newCompanyVal, True])
        else:
            yield renderScriptBlock(request, "settings.mako", "companyItem",
                                    False, "#company-school-wrapper", "prepend",
                                    args=[newCompanyId, newCompanyVal, True])


    @defer.inlineCallbacks
    def _editSchoolForm(self, request):
        encodedSchoolId = utils.getRequestArg(request, 'id')
        schoolId = utils.decodeKey(encodedSchoolId) if encodedSchoolId else None

        if schoolId:
            try:
                myId = request.getSession(IAuthInfo).username
                schoolVal = yield db.get(myId, 'entities', schoolId, "schools")
                schoolVal = schoolVal.column.value
                yield renderScriptBlock(request, "settings.mako", "schoolForm",
                                        False, "#addedu-dlg", "set",
                                        args=[schoolId, schoolVal])
                return
            except: pass

        yield renderScriptBlock(request, "settings.mako", "schoolForm",
                                False, "#addedu-dlg", "set")


    @defer.inlineCallbacks
    def _editSchool(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        remove = utils.getRequestArg(request, 'action') == 'd'
        encodedSchoolId = utils.getRequestArg(request, 'id', sanitize=False)
        schoolId = utils.decodeKey(encodedSchoolId) if encodedSchoolId else None

        if schoolId and remove:
            db.remove(myId, "entities", schoolId, "schools")
            request.write('$("#%s").remove();' % encodedSchoolId)
            return

        curYear = datetime.date.today().year
        try:
            year = int(utils.getRequestArg(request, 'year'))
            if not 1920 < year <= curYear:
                raise ValueError
        except (ValueError,TypeError):
            raise errors.InvalidRequest('Invalid graduation year')

        name = utils.getRequestArg(request, 'school')
        degree = utils.getRequestArg(request, 'degree')

        if not remove and not name:
            errors.MissingParams(['Name'])

        if schoolId:
            db.remove(myId, "entities", schoolId, "schools")

        newSchoolId = "%s:%s" % (year, name)
        newSchoolVal = degree
        db.insert(myId, "entities", newSchoolVal, newSchoolId, "schools")

        request.write('$$.dialog.close("addedu-dlg");')
        if schoolId:
            yield renderScriptBlock(request, "settings.mako", "schoolItem",
                                    False, "#"+encodedSchoolId, "replace",
                                    args=[newSchoolId, newSchoolVal, True])
        else:
            yield renderScriptBlock(request, "settings.mako", "schoolItem",
                                    False, "#company-school-wrapper", "append",
                                    args=[newSchoolId, newSchoolVal, True])


    @defer.inlineCallbacks
    def _updateExpertise(self, request):
        myId = request.getSession(IAuthInfo).username
        expertise = utils.getRequestArg(request, 'expertise[]', False, True)
        valid = []
        for x in expertise:
            decoded = x.decode('utf-8', 'replace')
            if len(decoded) > 50 or not re.match('^[\w-]*$', decoded):
                raise errors.InvalidRequest('Expertise can only be upto 50 characters long and can include numerals, alphabet and hyphens (-) only.')

        yield db.insert(myId, "entities", ','.join(expertise), "expertise", "expertise")
        request.write('$$.alerts.info("%s");' % _('Expertise information updated successfully!'))


    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1:
            action = request.postpath[0]
            if action == 'basic':
                d = self._editBasicInfo(request)
            elif action == 'work':
                d = self._editWorkInfo(request)
            elif action == 'company':
                d = self._editCompany(request)
            elif action == 'school':
                d = self._editSchool(request)
            elif action == 'personal':
                d = self._editPersonalInfo(request)
            elif action == "passwd":
                d = self._changePassword(request)
            elif action == "notify":
                d = self._updateNotifications(request)
            elif action == "expertise":
                d = self._updateExpertise(request)

        return self._epilogue(request, d)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._render(request)
        elif segmentCount == 1:
            segment = request.postpath[0]
            if segment == "company":
                d = self._editCompanyForm(request)
            elif segment == "school":
                d = self._editSchoolForm(request)

        return self._epilogue(request, d)
