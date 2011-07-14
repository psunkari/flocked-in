import shutil
import os
import time
import uuid
import hashlib
import datetime
import base64
import json
import re
import string
from email.mime.text     import MIMEText
from email.MIMEMultipart import MIMEMultipart

try:
    import cPickle as pickle
except:
    import pickle
from html5lib           import sanitizer
from ordereddict        import OrderedDict
from dateutil.tz        import gettz
from telephus.cassandra import ttypes

from twisted.internet   import defer, threads
from twisted.python     import log
from twisted.mail       import smtp

from social             import db, _, __, config, errors
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.constants   import INFINITY
from social.logging     import profile, dump_args


def md5(text):
    m = hashlib.md5()
    m.update(text)
    return m.hexdigest()


def supercolumnsToDict(supercolumns, ordered=False):
    retval = OrderedDict() if ordered else {}
    for item in supercolumns:
        name = item.super_column.name
        retval[name] = OrderedDict() if ordered else {}
        for col in item.super_column.columns:
            retval[name][col.name] = col.value
    return retval


def multiSuperColumnsToDict(superColumnsMap, ordered=False):
    retval = OrderedDict() if ordered else {}
    for key in superColumnsMap:
        columns =  superColumnsMap[key]
        retval[key] = supercolumnsToDict(columns, ordered=ordered)
    return retval


def multiColumnsToDict(columnsMap, ordered=False):
    retval = OrderedDict() if ordered else {}
    for key in columnsMap:
        columns = columnsMap[key]
        retval[key] = columnsToDict(columns, ordered=ordered)
    return retval


def columnsToDict(columns, ordered = False):
    retval = OrderedDict() if ordered else {}
    for item in columns:
        retval[item.column.name] = item.column.value
    return retval

def _sanitize(text):
    escape_entities = {':':"&#58;"}
    return sanitizer.escape(text, escape_entities).strip()

def getRequestArg(request, arg, sanitize=True, multiValued=False):
    if request.args.has_key(arg):
        if not multiValued:
            if sanitize:
                return _sanitize(request.args[arg][0])
            else:
                return request.args[arg][0]
        if sanitize:
            return [_sanitize(value) for value in request.args[arg]]
        else:
            return request.args[arg]

    else:
        return None


@defer.inlineCallbacks
def getValidEntityId(request, arg, type="user", columns=None):
    entityId = getRequestArg(request, arg, sanitize=False)
    if not entityId:
        raise errors.MissingParams([_('%s id') % _(type).capitalize()])

    entity = yield db.get_slice(entityId, "entities",
                                ["basic"].extend(columns if columns else []))
    if not entity:
        raise errors.InvalidEntity(type, entityId)

    entity = supercolumnsToDict(entity)
    basic = entity["basic"]

    if type != basic["type"]:
        raise errors.InvalidEntity(type, entityId)

    authinfo = request.getSession(IAuthInfo)
    myOrgId = authinfo.organization
    org = basic["org"] if basic["type"] != "org" else entityId
    if myOrgId != org:
        raise errors.EntityAccessDenied(type, entityId)

    defer.returnValue((entityId, entity))


@defer.inlineCallbacks
def getValidItemId(request, arg, type=None, columns=None):
    itemId = getRequestArg(request, arg, sanitize=False)
    itemType = type if type else "item"
    if not itemId:
        raise errors.MissingParams([_('%s id') % _(itemType).capitalize()])

    columns = [] if not columns else columns
    columns.extend(["meta", "attachments"])

    item = yield db.get_slice(itemId, "items", columns)
    if not item:
        raise errors.InvalidItem(itemType, itemId)

    item = supercolumnsToDict(item)
    meta = item["meta"]

    if type and meta["type"] != type:
        raise errors.InvalidItem(itemType, itemId)

    parentId = meta.get("parent", None)
    if parentId:
        parent = yield db.get_slice(parentId, "items", ["meta"])
        parent = supercolumnsToDict(parent)
        acl = parent["meta"]["acl"]
        owner = parent["meta"]["owner"]
    else:
        acl = meta["acl"]
        owner = meta["owner"]

    authinfo = request.getSession(IAuthInfo)
    myOrgId = authinfo.organization
    myId = authinfo.username
    relation = Relation(myId, [])
    yield defer.DeferredList([relation.initFriendsList(),
                              relation.initGroupsList()])
    if not checkAcl(myId, acl, owner, relation, myOrgId):
        raise errors.ItemAccessDenied(itemType, itemId)

    defer.returnValue((itemId, item))


@defer.inlineCallbacks
def getValidTagId(request, arg):
    tagId = getRequestArg(request, arg, sanitize=False)
    if not tagId:
        raise errors.MissingParams([_('Tag id')])

    orgId = request.getSession(IAuthInfo).organization
    tag = yield db.get_slice(orgId, "orgTags", [tagId])
    if not tag:
        raise errors.InvalidTag(tagId)

    tag = supercolumnsToDict(tag)
    defer.returnValue((tagId, tag))


def getRandomKey(prefix):
    key = prefix + "/" + str(uuid.uuid1())
    sha = hashlib.sha1()
    sha.update(key)
    return sha.hexdigest()


# XXX: We need something that can guarantee unique keys over trillion records
#      and must be printable (in logs etc;)
def getUniqueKey():
    u = uuid.uuid1()
    return base64.urlsafe_b64encode(u.bytes)[:-2]

@defer.inlineCallbacks
def createNewItem(request, itemType, ownerId=None, acl=None, subType=None,
                  ownerOrgId=None, groupIds = None):
    authinfo = request.getSession(IAuthInfo)
    owner = ownerId or authinfo.username
    org = ownerOrgId or authinfo.organization

    if not acl:
        acl = getRequestArg(request, "acl", sanitize=False)
        try:
            acl = json.loads(acl)
            orgs = acl.get("accept", {}).get("orgs", [])
            if len(orgs) > 1 :
                raise errors.PermissionDenied(_('Cannot grant access to other orgs on this item'))
            elif len(orgs) == 1 and orgs[0] != org:
                raise errors.PermissionDenied(_('Cannot grant access to other orgs on this item'))
        except:
            if not org:
                raise Exception("User does not belong to any company!")
            acl = {"accept":{"orgs":[org]}}

    acl = pickle.dumps(acl)
    item = {
        "meta": {
            "acl": acl,
            "type": itemType,
            "uuid": uuid.uuid1().bytes,
            "owner": owner,
            "timestamp": str(int(time.time()))
        },
        "followers": {owner: ''}
    }
    if subType:
        item["meta"]["subType"] = subType
    tmpFileIds = getRequestArg(request, 'fId', False, True)
    attachments = {}
    if tmpFileIds:
        attachments = yield _upload_files(tmpFileIds)
        if attachments:
            item["attachments"] = {}
            for attachmentId in attachments:
                timeuuid, fid, name, size, ftype = attachments[attachmentId]
                val = "%s:%s:%s:%s" %(encodeKey(timeuuid), name, size, ftype)
                item["attachments"][attachmentId] = val
    defer.returnValue ((item, attachments))


@defer.inlineCallbacks
def _upload_files(tmp_fileIds):
    attachments = {}
    if tmp_fileIds:
        cols = yield db.multiget_slice(tmp_fileIds, "tmp_files", ["fileId"])
        cols = multiColumnsToDict(cols)
        for tmpFileId in cols:
            attachmentId = getUniqueKey()
            timeuuid = uuid.uuid1().bytes
            location, name, size, ftype = cols[tmpFileId]['fileId'].split(':')

            if not os.path.lexists(location):
                log.msg('file doesnt exist')
                raise errors.uploadFailed()

            directory, fid = os.path.split(location)
            newlocation = os.path.join('data', fid[0:2], fid[2:4], fid[4:6], fid)
            try:
                file_meta = yield db.get(fid, "files", super_column="meta")
            except ttypes.NotFoundException:
                try:
                    directory, fname = os.path.split(newlocation)
                    os.makedirs(directory)
                except OSError:
                    pass
                try:
                    shutil.copy(location, newlocation)
                except OSError:
                    log.msg("can't move the file from %s to %s"% (location ,newlocation))
                    raise errors.uploadFailed()

                meta = {"meta": {"uri": newlocation}}
                yield db.batch_insert(fid, "files", meta)
            attachments[attachmentId] = (timeuuid, fid, name, size, ftype)
    defer.returnValue(attachments)


@defer.inlineCallbacks
def getFollowers(userKey, count=10):
    cols = yield db.get_slice(userKey, "followers", count=count)
    defer.returnValue(set(columnsToDict(cols).keys()))


@defer.inlineCallbacks
def getSubscriptions(userKey, count=10):
    cols = yield db.get_slice(userKey, "subscriptions", count=count)
    defer.returnValue(set(columnsToDict(cols).keys()))


@defer.inlineCallbacks
def getFriends(userKey, count=10):
    cols = yield db.get_slice(userKey, "connections", count=count)
    friends = set(supercolumnsToDict(cols).keys())
    defer.returnValue(set(friends))


@defer.inlineCallbacks
def getCompanyKey(userKey):
    cols = yield db.get_slice(userKey, "entities", ["org"], super_column="basic")
    cols = columnsToDict(cols)
    defer.returnValue(cols['org'])


@defer.inlineCallbacks
def getCompanyGroups(orgId):
    cols = yield db.get_slice(orgId, "orgGroups")
    cols = columnsToDict(cols)
    defer.returnValue(cols.keys())


@defer.inlineCallbacks
def expandAcl(userKey, acl, convOwnerId=None):
    keys = set()
    acl = pickle.loads(acl)
    accept = acl.get("accept", {})
    deny = acl.get('deny', {})
    deniedUsers = deny.get("users", [])

    #if acl in ["friends", "company", "public"]:
    if "users" in accept:
        for uid in accept["users"]:
            if uid not in deniedUsers:
                keys.add(uid)
    if "groups" in accept:
        groups = accept["groups"][:]
        for groupId in groups[:]:
            if groupId in deny.get("groups", []):
                groups.remove(groupId)
        groupMembers = yield db.multiget_slice(groups,"followers")
        groupMembers = multiColumnsToDict(groupMembers)
        for groupId in groupMembers:
            keys.update([uid for uid in groupMembers[groupId].keys() \
                            if uid not in deniedUsers])
        keys.update(groups)

    if any([typ in ["friends", "orgs", "public"] for typ in accept]):
        friends = yield getFriends(userKey, count=INFINITY)
        if "friends"  in accept and convOwnerId:
            friends1 = yield getFriends(convOwnerId, count=INFINITY)
            commonFriends = friends.intersection(friends1)
            keys.update([uid for uid in commonFriends if uid not in deniedUsers])
        else:
            keys.update([uid for uid in friends if uid not in deniedUsers])
    if any([typ in ["followers", "orgs", "public"] for typ in accept ]):
        followers = yield getFollowers(userKey, count=INFINITY)
        keys.update([uid for uid in followers if uid not in deniedUsers])
    if any([typ in ["orgs", "public"] for typ in accept]):
        companyKey = yield getCompanyKey(userKey)
        keys.update(set([companyKey]))
    defer.returnValue(keys)


def checkAcl(userId, acl, owner, relation, userOrgId=None):
    acl = pickle.loads(acl)
    deny = acl.get("deny", {})
    accept = acl.get("accept", {})
    # if userID is owner of the conversation, show the item irrespective of acl
    if userId == owner:
        return True

    if userId in deny.get("users", []) or \
       userOrgId in deny.get("org", []) or \
       (deny.get("friends", []) and owner in relation.friends) or \
       any([groupid in deny.get("groups", []) for groupid in relation.groups]):
        return False

    if "public" in accept:
        return True
    elif "orgs" in accept:
        return userOrgId in accept["orgs"]
    elif "groups" in accept:
        return any([groupid in accept["groups"] for groupid in relation.groups])
    elif "friends" in accept:
        return (userId == owner) or (owner in relation.friends)
    elif "followers" in accept:
        return (userId == owner) or (relation.subscriptions and owner in relation.subscriptions)
    elif "users" in accept:
        return userId in accept["users"]
    return False


def encodeKey(key):
    return "xX" + base64.urlsafe_b64encode(key).strip('=')


def decodeKey(key):
    if not key.startswith("xX"):
        return key

    length = len(key) - 2
    return base64.urlsafe_b64decode(key[2:] + ((length % 4) * '='))


# Return a count of unseen notifications a user has.
# XXX: Assuming a user would never have too many unseen notifications.
@defer.inlineCallbacks
def getLatestCounts(request, asJSON=True):
    authinfo = yield defer.maybeDeferred(request.getSession, IAuthInfo)
    myId = authinfo.username
    myOrgId = authinfo.organization

    latest = yield db.get_slice(myId, "latest")
    latest = supercolumnsToDict(latest)
    counts = dict([(key, len(latest[key])) for key in latest])

    groups = yield db.get_slice(myId, "entities", ['adminOfGroups'])
    groups = supercolumnsToDict(groups).get('adminOfGroups', {}).keys()
    if groups:
        counts.setdefault("groups", 0)
        cols = yield db.multiget_slice(groups, "latest")
        cols = multiSuperColumnsToDict(cols)
        for groupId in cols:
            for key in cols[groupId]:
                counts['groups'] += len(cols[groupId][key])

    if asJSON:
        defer.returnValue(json.dumps(counts))
    else:
        defer.returnValue(counts)


#
# Date and time formating utilities (format based on localizations)
#
def monthName(num, long=False):
    short = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    full = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December']
    return full[num-1] if long else short[num-1]


def weekName(num, long=False):
    short = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    full = ['Sunday', 'Monday', 'Tuesday', 'Thursday', 'Friday', 'Saturday']
    return full[num-1] if long else short[num-1]


def itemLink(itemId, itemType, classes=None):
    return "<span class='item %s'>" % (classes if classes else "") +\
           "<a class='ajax' href='/item?id=%s'>%s</a></span>"\
           % (itemId, _(itemType))


def userName(id, user, classes=None):
    return "<span class='user%s'>" % (' '+classes if classes else "") +\
           "<a class='ajax' href='/profile?id=%s'>%s</a></span>"\
           % (id, user["basic"]["name"])

def groupName(id, user, classes=None):
    return "<span><a class='ajax' href='/feed?id=%s'>%s</a></span>"\
           % (id, user["basic"]["name"])


def userAvatar(id, userInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    avatar = userInfo.get("basic", {}).get("avatar", None)
    sex = userInfo.get("basic", {}).get("sex", "M").lower()
    if avatar:
        imgType, itemId = avatar.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)
    else:
        sex = "m" if sex != "f" else "f"
        return "/rsrcs/img/avatar_%s_%s.png" % (sex, size)


def groupAvatar(id, groupInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    avatar = groupInfo.get("basic", {}).get("avatar", None)
    if avatar:
        imgType, itemId = avatar.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)
    else:
        return "/rsrcs/img/avatar_g_%s.png" % size


def companyLogo(orgInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    logo = orgInfo.get("basic", {}).get("logo", None)
    if logo:
        imgType, itemId = logo.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)
    else:
        return None


_urlRegEx = r'\b(([\w-]+(?::|&#58;)//?|www[.])[^\s()<>]+(?:\([\w\d]+\)|([^%s\s]|/)))'
_urlRegEx = _urlRegEx % re.sub(r'([-\\\]])', r'\\\1', string.punctuation)
_urlRegEx = re.compile(_urlRegEx)
_newLineRegEx = r'\r\n|\n'
_newLineRegEx = re.compile(_newLineRegEx)
def normalizeText(text):
    global _urlRegEx
    def addAnchor(m):
        if (m.group(2) == "www."):
            return '<a class="c-link" target="_blank" href="http://%s">%s</a>'%(m.group(0), m.group(0))
        elif (m.group(2).startswith("http")):
            return '<a class="c-link" target="_blank" href="%s">%s</a>'%(m.group(0), m.group(0))
        else:
            return m.group(0)

    urlReplaced = _urlRegEx.sub(addAnchor, text)
    return _newLineRegEx.sub('<br/>', urlReplaced).strip().lstrip().replace("\r\n", "<br/>")


def simpleTimestamp(timestamp, timezone='Asia/Kolkata'):
    tzinfo = gettz(timezone)
    if not tzinfo:
        tzinfo = gettz('Asia/Kolkata')

    current = datetime.datetime.now(tzinfo)
    ts = datetime.datetime.fromtimestamp(timestamp, tzinfo)
    delta = current - ts

    # Map used for localization
    params = {'minutes': ts.minute, '24hour': ts.hour,
              '12hour': 12 if not (ts.hour % 12) else (ts.hour % 12),
              'month': _(monthName(ts.month, True)), 'year': ts.year,
              'ampm': "am" if ts.hour < 11 else "pm",
              'dow': _(weekName(ts.weekday(), True)), 'date': ts.day}
    tooltip = _("%(dow)s, %(month)s %(date)s, %(year)s at %(12hour)s:%(minutes)02d%(ampm)s") % params

    if delta < datetime.timedelta(days=1):
        if delta.seconds < 60:
            formatted = _("a few seconds ago")
        elif delta.seconds < 3600:
            formatted = _("%s minutes ago") % (delta.seconds/60)
        elif delta.seconds < 7200:
            formatted = _("about one hour ago")
        else:
            formatted = _("%s hours ago") % (delta.seconds/3600)
    else:
        if current.year == ts.year:
            formatted = _("%(month)s %(date)s at %(12hour)s:%(minutes)02d%(ampm)s") % params
        else:
            formatted = _("%(month)s %(date)s, %(year)s at %(12hour)s:%(minutes)02d%(ampm)s") % params

    return "<abbr class='timestamp' title='%s' _ts='%s'>%s</abbr>" %(tooltip, timestamp, formatted)


def toSnippet(comment):
    commentSnippet = []
    length = 0
    words = comment.split()

    # If it's a single word (eg:link) only make sure that
    # the word isn't too long.
    if len(words) == 1:
        if len(words[0]) > 35:
            return words[0][0:30] + "&hellip;"
        else:
            return words[0]

    # More than one words. Break only at spaces.
    for word in words:
        if length+len(word) > 35:
            commentSnippet.append("&hellip;")
            break
        commentSnippet.append(word)
        length += len(word)
    return " ".join(commentSnippet)


def uuid1(node=None, clock_seq=None, timestamp=None):
    if not timestamp:
        nanoseconds = int(time.time() * 1e9)
        # 0x01b21dd213814000 is the number of 100-ns intervals between the
        # UUID epoch 1582-10-15 00:00:00 and the Unix epoch 1970-01-01 00:00:00.
        timestamp = int(nanoseconds//100) + 0x01b21dd213814000L
    else:
        nanoseconds = int(timestamp*1e9)
        timestamp = int(nanoseconds/100) + 0x01b21dd213814000L

    if clock_seq is None:
        import random
        clock_seq = random.randrange(1<<14L) # instead of stable storage
    time_low = timestamp & 0xffffffffL
    time_mid = (timestamp >> 32L) & 0xffffL
    time_hi_version = (timestamp >> 48L) & 0x0fffL
    clock_seq_low = clock_seq & 0xffL
    clock_seq_hi_variant = (clock_seq >> 8L) & 0x3fL
    if node is None:
        node = uuid.getnode()
    return uuid.UUID(fields=(time_low, time_mid, time_hi_version,
                        clock_seq_hi_variant, clock_seq_low, node), version=1)


@defer.inlineCallbacks
def existingUser(emailId):
    count = yield db.get_count(emailId, "userAuth")
    if count:
        defer.returnValue(True)
    defer.returnValue(False)


@defer.inlineCallbacks
def addUser(emailId, displayName, passwd, orgKey, jobTitle = None, timezone=None):
    userId = getUniqueKey()

    userInfo = {'basic': {'name': displayName, 'org':orgKey,
                          'type': 'user', 'emailId':emailId}}
    userAuthInfo = {"passwordHash": md5(passwd), "org": orgKey, "user": userId}

    if jobTitle:
        userInfo["basic"]["jobTitle"] = jobTitle
    if timezone:
        userInfo["basic"]["timezone"] = timezone

    yield db.insert(orgKey, "orgUsers", '', userId)
    yield db.batch_insert(userId, "entities", userInfo)
    yield db.batch_insert(emailId, "userAuth", userAuthInfo)
    yield db.insert(orgKey, "displayNameIndex", "", displayName.lower()+ ":" + userId)
    yield db.insert(orgKey, "nameIndex", "", displayName.lower()+ ":" + userId)

    defer.returnValue(userId)


@defer.inlineCallbacks
def removeUser(userId, userInfo=None):
    if not userInfo:
        cols = yield db.get_slice(userId, "entities", ["basic"])
        userInfo = supercolumnsToDict(cols)
    emailId = userInfo["basic"].get("emailId", None)
    displayName = userInfo["basic"].get("name", None)
    orgKey = userInfo["basic"]["org"]

    yield db.remove(emailId, "userAuth")
    yield db.remove(orgKey, "displayNameIndex", ":".join([displayName.lower(), userId]))
    yield db.remove(orgKey, "orgUsers", userId)
    yield db.remove(orgKey, "blockedUsers", userId)
    #unfriend - remove all pending requests
    #clear displayName index
    #clear nameindex
    #unfollow
    #unsubscribe from all groups


@defer.inlineCallbacks
def getAdmins(entityId):
    cols = yield db.get_slice(entityId, "entities", ["admins"])
    admins = supercolumnsToDict(cols).get("admins", {}).keys()
    defer.returnValue(admins)


@defer.inlineCallbacks
def isAdmin(userId, entityId):
    admins = yield getAdmins(entityId)
    if not admins:
        defer.returnValue(False)
    defer.returnValue(userId in admins)


@profile
@defer.inlineCallbacks
@dump_args
def deleteNameIndex(userKey, name, targetKey):
    if name:
        yield db.remove(userKey, "nameIndex", ":".join([name.lower(), targetKey]))


@profile
@defer.inlineCallbacks
@dump_args
def updateDisplayNameIndex(userKey, targetKeys, newName, oldName):
    calls = []
    muts = {}

    for targetKey in targetKeys:
        if oldName or newName:
            muts[targetKey] = {'displayNameIndex':{}}
        if oldName:
            colName = oldName.lower() + ":" + userKey
            muts[targetKey]['displayNameIndex'][colName] = None
        if newName:
            colName = newName.lower() + ':' + userKey
            muts[targetKey]['displayNameIndex'][colName] = ''
    if muts:
        yield db.batch_mutate(muts)


@profile
@defer.inlineCallbacks
@dump_args
def updateNameIndex(userKey, targetKeys, newName, oldName):
    muts = {}
    for targetKey in targetKeys:
        if oldName or newName:
            muts[targetKey] = {'nameIndex':{}}
        if oldName :
            colName = oldName.lower() + ":" + userKey
            muts[targetKey]['nameIndex'][colName] = None
        if newName:
            colName = newName.lower() + ":" + userKey
            muts[targetKey]['nameIndex'][colName] = ''
    if muts:
        yield db.batch_mutate(muts)


@profile
@defer.inlineCallbacks
@dump_args
def sendmail(toAddr, subject, textPart, htmlPart=None,
             fromAddr='noreply@flocked.in'):
    if htmlPart:
        msg = MIMEMultipart('alternative')
        msg.preamble = 'This is a multi-part message in MIME format.'
        
        msgText = MIMEText(textPart)
        msg.attach(msgText)

        msgText = MIMEText(htmlPart, 'html')
        msg.attach(msgText)
    else:
        msg = MIMEText(textPart)

    msg['Subject'] = subject
    msg['From'] = "FlockedIn Team <%s>" % fromAddr
    msg['To'] = toAddr

    message = msg.as_string()
    host = config.get('SMTP', 'Host')
    yield smtp.sendmail(host, fromAddr, toAddr, message)


SUFFIXES = {1000: ['KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
            1024: ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB']}

def approximate_size(size, a_kilobyte_is_1024_bytes=False):
    '''Convert a file size to human-readable form.
    Keyword arguments:
    size -- file size in bytes
    a_kilobyte_is_1024_bytes -- if True (default), use multiples of 1024
                                if False, use multiples of 1000
    Returns: string
    '''
    if size < 0:
        raise ValueError('number must be non-negative')

    multiple = 1024 if a_kilobyte_is_1024_bytes else 1000
    for suffix in SUFFIXES[multiple]:
        size /= multiple
        if size < multiple:
            return '{0:.1f} {1}'.format(size, suffix)

    raise ValueError('number too large')
