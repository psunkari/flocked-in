import PythonMagick
import imghdr
import time
import uuid
from random                 import sample
import datetime
import json
import re

try:
    import cPickle as pickle
except:
    import pickle

from twisted.web            import resource, server, http
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social                 import db, utils, base, plugins, _, __, search
from social                 import constants, feed, errors
from social                 import template as t
from social.relations       import Relation
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
def saveAvatarItem(entityId, orgId, data, isLogo=False):
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
    acl = pickle.dumps({"accept":{"orgs":[orgId]}})
    item = {
        "meta": {"owner": entityId, "acl": acl, "type": "image"},
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

notifyItemFC = notifyItemRFC = notifyItemUFC = 18
notifyMyItemFC = notifyMyItemRFC = notifyMyItemUFC = 19

notifyKW = 20

notifyItemEI = notifyItemEA = 21
notifyMyItemEI = notifyMyItemEA = 22

# Total number of notification types and default setting
_notificationsCount = 23
defaultNotify = "3" * _notificationsCount

# Notification medium
notifyByMail = 1
notifyBySMS = 2

# Names of each notification type (by index as given above)
_notifyNames = ['friendRequest', 'friendAccept', 'follower', 'newMember',
    'groupRequest', 'groupAccept', 'groupInvite', 'groupNewMember',
    'myItemTag', 'myItemComment', 'myItemlike', 'itemCommentLike',
    'itemComment', 'mention', 'itemRequests',
    'messageConv', 'messageMessage', 'messageAccessChange',
    'itemFlagged', 'myItemFlagged', 'keywordMatch', 'eventInvite',
    'eventAttend']

# List of notifications that currently must not be displayed to the user
_hiddenNotifys = [notifyFR, notifyFA, notifyMention, notifyItemRequests, notifyKW]

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
    _templates = ['settings.mako']
    resources = {}


    @defer.inlineCallbacks
    def _changePassword(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

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

        emailId = args["me"].basic["emailId"]
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
        data = {}
        to_remove = []

        me = yield db.get_slice(myId, 'entities')
        me = base.Entity(myId)
        yield me.fetchData([])
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

        t.renderScriptBlock(request, "settings.mako", "right",
                            False, ".right-contents", "set", **args)
        me.update({'personal':data})
        yield search.solr.updatePeopleIndex(myId, me, orgId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _editWorkInfo(self, request):
        # Contact information at work.
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization

        me = base.Entity(myId)
        yield me.fetchData([])
        data = {}
        to_remove = []

        for field in ["phone", "mobile"]:
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
            yield db.batch_remove({"entities":[myId]}, names=to_remove, supercolumn='contact')

        contactInfo = me.get('contact', {})
        if any([contactInfo.get(x, None) != data.get(x, None) for x in ["phone", "mobile"]]):
            request.write('$$.alerts.info("%s");' % _('Profile updated'))

        args = {"detail": "", "me": me}
        suggestedSections = yield self._checkProfileCompleteness(request, myId, args)
        tmp_suggested_sections = {}
        for section, items in suggestedSections.iteritems():
            if len(suggestedSections[section]) > 0:
                tmp_suggested_sections[section] = items
        args.update({'suggested_sections':tmp_suggested_sections})

        t.renderScriptBlock(request, "settings.mako", "right",
                            False, ".right-contents", "set", **args)
        me.update({'contact':data})
        yield search.solr.updatePeopleIndex(myId, me, orgId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _editBasicInfo(self, request):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization

        userInfo = {"basic":{}}
        to_remove = []
        basicUpdatedInfo, basicUpdated = {}, False

        me = base.Entity(myId)
        yield me.fetchData([])

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
            if me.basic.get(cn, None) != userInfo['basic'].get(cn, None):
                basicUpdated = True

        # Update name indicies of organization.
        nameIndexKeys = [orgId]
        nameIndicesDeferreds = []
        oldNameParts = []
        newNameParts = []
        for field in ["name", "lastname", "firstname"]:
            if field in basicUpdatedInfo:
                newNameParts.extend(basicUpdatedInfo[field].split())
                oldNameParts.extend(me.basic.get(field, '').split())
                if field == 'name':
                    d1 = utils.updateDisplayNameIndex(myId, nameIndexKeys,
                                                      basicUpdatedInfo[field],
                                                      me.basic.get(field, None))
                    nameIndicesDeferreds.append(d1)
        d = utils.updateNameIndex(myId, nameIndexKeys,
                                  " ".join(newNameParts),
                                  " ".join(oldNameParts))
        nameIndicesDeferreds.append(d)

        # Avatar (display picture)
        dp = utils.getRequestArg(request, "dp", sanitize=False)
        if dp:
            avatar = yield saveAvatarItem(myId, orgId, dp)
            userInfo["basic"]["avatar"] = avatar
            me.basic["avatar"] = avatar
            avatarURI = utils.userAvatar(myId, me)
            basicUpdatedInfo["avatar"] = avatarURI
            basicUpdated = True
        if userInfo["basic"]:
            yield db.batch_insert(myId, "entities", userInfo)
            me.basic.update(userInfo['basic'])
            yield search.solr.updatePeopleIndex(myId, me, orgId)

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

        t.renderScriptBlock(request, "settings.mako", "right",
                            False, ".right-contents", "set", **args)


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

        #getBasicArgs fetches basic user info. fetch all data.
        me = base.Entity(myId)
        yield me.fetchData([])
        args['me'] = me

        if script and landing:
            t.render(request, "settings.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "settings.mako", "layout",
                                landing, "#mainbar", "set", **args)

        if script:
            t.renderScriptBlock(request, "settings.mako", "settingsTitle",
                                landing, "#settings-title", "set", **args)

            handlers={"onload": "$$.menu.selectItem('%s');" % detail}
            if detail == "basic":
                handlers["onload"] += "$$.ui.bindFormSubmit('#settings-form');"
                t.renderScriptBlock(request, "settings.mako", "editBasicInfo",
                                    landing, "#settings-content", "set", True,
                                    handlers = handlers, **args)

            elif detail == "work":
                t.renderScriptBlock(request, "settings.mako", "editWork",
                                    landing, "#settings-content", "set", True,
                                    handlers=handlers, **args)

            elif detail == "personal":
                t.renderScriptBlock(request, "settings.mako", "editPersonal",
                                    landing, "#settings-content", "set", True,
                                    handlers=handlers, **args)

            elif detail == "passwd":
                t.renderScriptBlock(request, "settings.mako", "changePasswd",
                                    landing, "#settings-content", "set", True,
                                    handlers=handlers, **args)

            elif detail == "notify":
                t.renderScriptBlock(request, "settings.mako", "filterNotifications",
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
            t.renderScriptBlock(request, "settings.mako", "right",
                                landing, ".right-contents", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            t.render(request, "settings.mako", **args)


    @defer.inlineCallbacks
    def _checkProfileCompleteness(self, request, myId, args):
        landing = not self._ajax
        detail = args["detail"]
        suggestedSections = {}

        # Check Basic
        requiredFields = ["jobTitle", "timezone"]
        jobTitle = args["me"].basic.get("jobTitle", None)
        myTimezone = args["me"].basic.get("timezone", None)
        suggestedSections["basic"] = []
        if jobTitle is None:
            suggestedSections["basic"].append("Add a job title")
        if myTimezone is None:
            suggestedSections["basic"].append("Configure your timezone")

        # Check Work
        suggestedSections["work"] = []
        if "contactInfo" not in args:
            res = yield db.get_slice(myId, "entities", ['contact'])
            contactInfo = utils.supercolumnsToDict(res).get("contact", {})
        else:
            contactInfo = args["contactInfo"]

        phone = contactInfo.get('phone', None)
        if not phone:
            suggestedSections["work"].append("Add a work phone")

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
                yield t.renderScriptBlock(request, "settings.mako", "companyForm",
                                        False, "#"+encodedCompanyId, "replace",
                                        args=[companyId, companyVal])
                return
            except: pass

        yield t.renderScriptBlock(request, "settings.mako", "companyForm",
                                False, "#addemp-wrap", "set")


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

        today = datetime.date.today()
        try:
            startYear = int(utils.getRequestArg(request, 'startyear'))
            startMonth = int(utils.getRequestArg(request, 'startmonth'))
            startDay = datetime.date(startYear, startMonth, 1)
        except (ValueError, TypeError):
            raise errors.InvalidRequest('Please give a valid start month and year')

        try:
            endYear = utils.getRequestArg(request, 'endyear')
            if not endYear:
                endYear = 9999
                endMonth = 12
            else:
                endYear = int(endYear)
                endMonth = int(utils.getRequestArg(request, 'endmonth'))
            endDay = datetime.date(endYear, endMonth, 1)
        except (ValueError, TypeError):
            raise errors.InvalidRequest('Please give a valid end month and year')

        if startDay > today or startDay > endDay or (endDay > today and endYear != 9999):
            raise errors.InvalidRequest('The start month/year and end month/year are invalid!')

        name = utils.getRequestArg(request, 'company')
        title = utils.getRequestArg(request, 'title')

        if not remove and not name:
            errors.MissingParams(['Name'])

        if companyId:
            db.remove(myId, "entities", companyId, "companies")

        newCompanyId = "%s%s:%s%s:%s" % (endYear, endMonth, startYear, startMonth, name)
        newCompanyVal = title
        db.insert(myId, "entities", newCompanyVal, newCompanyId, "companies")

        if companyId:
            yield t.renderScriptBlock(request, "settings.mako", "companyItem",
                                    False, "#"+encodedCompanyId, "replace",
                                    args=[newCompanyId, newCompanyVal])
        else:
            onload = """$('#company-empty-msg').remove();"""+\
                     """$('#addemp-wrap').replaceWith('<div id="addemp-wrap"><button class="button ajax" id="addedu-button" data-ref="/settings/company">Add Company</button></div>');"""
            yield t.renderScriptBlock(request, "settings.mako", "companyItem",
                                    False, "#companies-wrapper", "append", True,
                                    handlers={'onload': onload},
                                    args=[newCompanyId, newCompanyVal])


    @defer.inlineCallbacks
    def _editSchoolForm(self, request):
        encodedSchoolId = utils.getRequestArg(request, 'id')
        schoolId = utils.decodeKey(encodedSchoolId) if encodedSchoolId else None

        if schoolId:
            try:
                myId = request.getSession(IAuthInfo).username
                schoolVal = yield db.get(myId, 'entities', schoolId, "schools")
                schoolVal = schoolVal.column.value
                yield t.renderScriptBlock(request, "settings.mako", "schoolForm",
                                        False, "#"+encodedSchoolId, "replace",
                                        args=[schoolId, schoolVal])
                return
            except: pass

        yield t.renderScriptBlock(request, "settings.mako", "schoolForm",
                                False, "#addedu-wrap", "set")


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

        if schoolId:
            yield t.renderScriptBlock(request, "settings.mako", "schoolItem",
                                    False, "#"+encodedSchoolId, "replace",
                                    args=[newSchoolId, newSchoolVal])
        else:
            onload = """$('#school-empty-msg').remove();"""+\
                     """$('#addedu-wrap').replaceWith('<div id="addedu-wrap"><button class="button ajax" id="addedu-button" data-ref="/settings/school">Add School</button></div>');"""
            yield t.renderScriptBlock(request, "settings.mako", "schoolItem",
                                    False, "#schools-wrapper", "append", True,
                                    handlers={'onload': onload},
                                    args=[newSchoolId, newSchoolVal])


    @defer.inlineCallbacks
    def _updateExpertise(self, request, remove=False):
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        expertise = utils.getRequestArg(request, 'expertise', False)
        if not expertise:
            raise errors.MissingParams(['Expertise'])

        if not remove:
            decoded = expertise.decode('utf-8', 'replace')
            if len(decoded) > 50 or not re.match('^[\w-]*$', decoded):
                raise errors.InvalidRequest('Expertise can only be upto 50 characters long and can include numerals, alphabet and hyphens (-) only.')

            yield db.insert(myId, "entities", '', expertise, "expertise")

        else:
            yield db.remove(myId, "entities", utils.decodeKey(expertise), "expertise")

        me = base.Entity(myId)
        yield me.fetchData([])
        expertise = me.get('expertise')

        onload = "$('#expertise-textbox').val('');"
        yield t.renderScriptBlock(request, "settings.mako", "_expertise",
                                False, "#expertise-container", "set", True,
                                handlers={"onload": onload}, args=[expertise])

        yield search.solr.updatePeopleIndex(myId, me, orgId)



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
            elif action == "unexpertise":
                d = self._updateExpertise(request, True)

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
