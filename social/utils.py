
import time
import uuid
import hashlib
import datetime
import base64
import json
import re
import string
try:
    import cPickle as pickle
except:
    import pickle

from ordereddict        import OrderedDict
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, _, __
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


def getRequestArg(request, arg):
    if request.args.has_key(arg):
        return request.args[arg][0]
    else:
        return None


@defer.inlineCallbacks
def getValidEntityId(request, arg, type="user"):
    entityId = getRequestArg(request, arg)
    if not entityId:
        raise errors.MissingParam()
    try:
        col = yield Db.get(entityId, "entities", "type", "basic")
        if col.column.value == type:
            defer.returnValue(entityId)
        raise errors.InvalidEntity()
    except Exception, e:
        log.err(e)
        raise errors.InvalidEntity()


@defer.inlineCallbacks
def getValidItemId(request, arg, columns=[], type=None):
    itemId = getRequestArg(request, arg)
    if not itemId:
        raise errors.MissingParam()

    item = yield Db.get_slice(itemId, "items", ["meta"].extend(columns))
    if not item:
        raise errors.InvalidEntity()

    item = supercolumnsToDict(item)
    if not type:
        defer.returnValue((itemId, item))
    elif type and item["meta"].get("type", None) == type:
        defer.returnValue((itemId, item))
    else:
        raise errors.InvalidEntity()


@defer.inlineCallbacks
def getValidTagId(request, arg, orgId=None):
    tagId = getRequestArg(request, arg)
    if not tagId:
        raise errors.MissingParam()

    if not orgId:
        orgId = request.getSession(IAuthInfo).organization

    tag = yield Db.get_slice(orgId, "orgTags", [tagId])
    if not tag:
        raise errors.InvalidTag()

    tag = supercolumnsToDict(tag)
    defer.returnValue((tagId, tag))


# TODO
def areFriendlyDomains(one, two):
    return True


def createACL(request):
    return None


def getRandomKey(prefix):
    key = prefix + "/" + str(uuid.uuid1())
    sha = hashlib.sha1()
    sha.update(key)
    return sha.hexdigest()


# XXX: We need something that can guarantee unique keys over trillion records.
def getUniqueKey():
    u = uuid.uuid1()
    return base64.urlsafe_b64encode(u.bytes)[:-2]


@defer.inlineCallbacks
def createNewItem(request, itemType, ownerId=None, acl=None, subType=None,
                  ownerOrgId=None, groupIds = None):
    owner = ownerId or request.getSession(IAuthInfo).username
    if not ownerOrgId:
        ownerOrgId = request.getSession(IAuthInfo).organization
    if not ownerOrgId:
        col = yield Db.get(owner, "entities", "org", "basic")
        ownerOrgId = col.column.value

    if not acl:
        acl = getRequestArg(request, "acl")
        try:
            acl = json.loads(acl);
        except:
            acl = {"accept":{"orgs":[ownerOrgId]}}

    acl = pickle.dumps(acl)
    meta = {
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
        meta["meta"]["subType"] = subType
    defer.returnValue(meta)


@defer.inlineCallbacks
def getFollowers(userKey, count=10):
    cols = yield Db.get_slice(userKey, "followers", count=count)
    defer.returnValue(set(columnsToDict(cols).keys()))


@defer.inlineCallbacks
def getSubscriptions(userKey, count=10):
    cols = yield Db.get_slice(userKey, "subscriptions", count=count)
    defer.returnValue(set(columnsToDict(cols).keys()))


@defer.inlineCallbacks
def getFriends(userKey, count=10):
    cols = yield Db.get_slice(userKey, "connections", count=count)
    friends = set(supercolumnsToDict(cols).keys())
    defer.returnValue(set(friends))


@defer.inlineCallbacks
def getCompanyKey(userKey):
    cols = yield Db.get_slice(userKey, "entities", ["org"], super_column="basic")
    cols = columnsToDict(cols)
    defer.returnValue(cols['org'])

@defer.inlineCallbacks
def getCompanyGroups(orgId):
    cols = yield Db.get_slice(orgId, "orgGroups")
    cols = columnsToDict(cols)
    defer.returnValue(cols.keys())


@defer.inlineCallbacks
def expandAcl(userKey, acl, convOwnerId=None):
    keys = set()
    acl = pickle.loads(acl)
    accept = acl.get("accept", {})
    deny = acl.get('deny', {})

    #if acl in ["friends", "company", "public"]:
    if "users" in accept:
        for uid in accept["users"]:
            if uid not in deny.get("users", []) :
                keys.update(accept["users"])
    if "groups" in accept:
        groups = accept["groups"][:]
        for groupId in groups[:]:
            if groupId in deny.get("groups", []):
                groups.remove(groupId)
        groupMembers = yield Db.multiget_slice(groups,"followers")
        groupMembers = multiColumnsToDict(groupMembers)
        for groupId in groupMembers:
            keys.update(set(groupMembers[groupId].keys()))
        keys.update(groups)

    if any([typ in ["friends", "orgs", "public"] for typ in accept]):
        friends = yield getFriends(userKey, count=INFINITY)
        if "friends"  in accept and convOwnerId:
            friends1 = yield getFriends(convOwnerId, count=INFINITY)
            commonFriends = friends.intersection(friends1)
            keys.update(commonFriends)
        else:
            keys.update(friends)
    if any([typ in ["orgs", "public"] for typ in accept]):
        companyKey = yield getCompanyKey(userKey)
        followers = yield getFollowers(userKey, count=INFINITY)
        keys.update(followers)
        keys.update(set([companyKey]))
    defer.returnValue(keys)


def checkAcl(userId, acl, owner, relation, userOrgId=None, userGroups=[]):

    acl = pickle.loads(acl)
    deny = acl.get("deny", {})
    accept = acl.get("accept", {})

    # if userID is owner of the conversation, show the item irrespective of acl
    #if userId == owner:
    #    return True

    if userId in deny.get("users", []) or \
       userOrgId in deny.get("org", []) or \
       (deny.get("friends", []) and owner in relation.friends) or \
       any([groupid in deny.get("groups", []) for groupid in relation.subscriptions]):
        return False

    if "public" in accept:
        return True
    elif "orgs" in accept:
        return userOrgId in accept["orgs"]
    elif "groups" in accept:
        return any([groupid in accept["groups"] for groupid in userGroups])
    elif "friends" in accept:
        return (userId == owner) or (owner in relation.friends)
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


def userAvatar(id, userInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    avatar = userInfo.get("basic", {}).get("avatar", None)
    sex = userInfo.get("basic", {}).get("sex", "M").lower()
    if avatar:
        imgType, itemId = avatar.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)
    else:
        sex = "m" if sex != "f" else "f"
        return "/public/images/avatar_%s_%s.png" % (sex, size)

    return None

def companyLogo(orgInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    logo = orgInfo.get("basic", {}).get("logo", None)
    if logo:
        imgType, itemId = logo.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)
    else:
        return None


_urlRegEx = r'\b(([\w-]+://?|www[.])[^\s()<>]+(?:\([\w\d]+\)|([^%s\s]|/)))'
_urlRegEx = _urlRegEx % re.sub(r'([-\\\]])', r'\\\1', string.punctuation)
_urlRegEx = re.compile(_urlRegEx)
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
    return urlReplaced.strip().lstrip().replace("\r\n", "<br/>")


def simpleTimestamp(timestamp):
    current = int(time.time())
    delta = current - timestamp

    ts = time.localtime(timestamp)

    # Map used for localization
    params = {'minutes': ts.tm_min, '24hour': ts.tm_hour,
              '12hour': 12 if not (ts.tm_hour % 12) else (ts.tm_hour % 12),
              'month': _(monthName(ts.tm_mon, True)), 'year': ts.tm_year,
              'ampm': "am" if ts.tm_hour < 11 else "pm",
              'dow': _(weekName(ts.tm_wday, True)), 'date': ts.tm_mday}
    tooltip = _("%(dow)s, %(month)s %(date)s, %(year)s at %(12hour)s:%(minutes)02d%(ampm)s") % params

    if delta < 86400:
        if delta < 60:
            formatted = _("a few seconds ago")
        elif delta < 3600:
            formatted = _("%s minutes ago") % (delta/60)
        elif delta < 7200:
            formatted = _("about one hour ago")
        else:
            formatted = _("%s hours ago") % (delta/3600)
    else:
        cs = time.localtime(current)
        if cs.tm_year == ts.tm_year:
            formatted = _("%(month)s %(date)s at %(12hour)s:%(minutes)02d%(ampm)s") % params
        else:
            formatted = _("%(month)s %(date)s, %(year)s at %(12hour)s:%(minutes)02d%(ampm)s") % params

    return "<abbr class='timestamp' title='%s' _ts='%s'>%s</abbr>" %(tooltip, timestamp, formatted)


def toSnippet(comment):
    commentSnippet = []
    length = 0
    for word in comment.replace(":", "").split():
        if length +len(word)> 20:
            commentSnippet.append(" ...")
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
    count = yield Db.get_count(emailId, "userAuth")
    if count:
        defer.returnValue(True)
    defer.returnValue(False)

@defer.inlineCallbacks
def addUser(emailId, displayName, passwd, orgKey, jobTitle = None):
    userId = getUniqueKey()

    userInfo = {'basic': {'name': displayName, 'org':orgKey,
                          'type': 'user', 'emailId':emailId}}
    userAuthInfo = {"passwordHash": md5(passwd), "org": orgKey, "user": userId}

    if jobTitle:
        userInfo["basic"]["jobTitle"] = jobTitle

    yield Db.insert(orgKey, "orgUsers", '', userId)
    yield Db.batch_insert(userId, "entities", userInfo)
    yield Db.batch_insert(emailId, "userAuth", userAuthInfo)
    yield Db.insert(orgKey, "displayNameIndex", "", displayName.lower()+ ":" + userId)

    defer.returnValue(userId)


@defer.inlineCallbacks
def removeUser(userId, userInfo=None):

    if not userInfo:
        cols = yield Db.get_slice(userId, "entities", ["basic"])
        userInfo = supercolumnsToDict(cols)
    emailId = userInfo["basic"].get("emailId", None)
    displayName = userInfo["basic"].get("name", None)
    orgKey = userInfo["basic"]["org"]

    yield Db.remove(emailId, "userAuth")
    yield Db.remove(orgKey, "displayNameIndex", ":".join([displayName.lower(), userId]))
    yield Db.remove(orgKey, "orgUsers", userId)
    yield Db.remove(orgKey, "blockedUsers", userId)
    #unfriend - remove all pending requests
    #clear displayName index
    #clear nameindex
    #unfollow
    #unsubscribe from all groups



@defer.inlineCallbacks
def getAdmins(entityId):
    cols = yield Db.get_slice(entityId, "entities", ["admins"])
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
        yield Db.remove(userKey, "nameIndex", ":".join([name.lower(), targetKey]))


@profile
@defer.inlineCallbacks
@dump_args
def _updateDisplayNameIndex(userKey, targetKey, newName, oldName):
    calls = []
    if oldName:
        d1 =  Db.remove(targetKey, "displayNameIndex", oldName.lower() + ":" + userKey)
        calls.append(d1)
    if newName:
        d2 =  Db.insert(targetKey, "displayNameIndex", "", newName.lower() + ':' + userKey)
        calls.append(d2)
    if calls:
        yield defer.DeferredList(calls)


@profile
@defer.inlineCallbacks
@dump_args
def updateDisplayNameIndex(userKey, targetKeys, newName, oldName):
    calls = []
    for targetKey in targetKeys:
        d = _updateDisplayNameIndex(userKey, targetKey, newName, oldName)
        calls.append(d)
    yield defer.DeferredList(calls)


@profile
@defer.inlineCallbacks
@dump_args
def _updateNameIndex(userKey, targetKey, newName, oldName):
    calls = []
    if oldName:
        d1 =  Db.remove(targetKey, "nameIndex", oldName.lower() + ":" + userKey)
        calls.append(d1)
    if newName:
        d2 =  Db.insert(targetKey, "nameIndex", "", newName.lower() + ":" + userKey)
        calls.append(d2)
    if calls:
        yield defer.DeferredList(calls)


@profile
@defer.inlineCallbacks
@dump_args
def updateNameIndex(userKey, targetKeys, newName, oldName):
    calls = []
    for targetKey in targetKeys:
        d = _updateNameIndex(userKey, targetKey, newName, oldName)
        calls.append(d)
    yield defer.DeferredList(calls)
