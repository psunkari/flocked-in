
import time
import uuid
import hashlib
import datetime
import base64

from ordereddict        import OrderedDict
from twisted.internet   import defer
from twisted.python     import log

from social             import Db, _, __
from social.constants   import INFINITY


def md5(text):
    m = hashlib.md5()
    m.update(text)
    return m.hexdigest()


def supercolumnsToDict(supercolumns, ordered=False):
    retval = OrderedDict() if ordered else {}
    for item in supercolumns:
        name = item.super_column.name
        retval[name] = {}
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
def getValidUserKey(request, arg):
    userKey = getRequestArg(request, arg)
    if not userKey:
        raise errors.MissingParam()

    try:
        col = yield Db.get(userKey, "users", "name", "basic")
        defer.returnValue(userKey)
    except Exception, e:
        log.err(e)
        raise errors.InvalidUser()


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
    cols = yield Db.get_slice(userKey, "users", ["org"], super_column="basic")
    cols = columnsToDict(cols)
    defer.returnValue(cols['org'])


@defer.inlineCallbacks
def expandAcl(userKey, acl, parentUserKey=None):
    keys = set()
    if acl in ["friends", "company", "public"]:
        friends = yield getFriends(userKey, count=INFINITY)
        if acl == "friends" and parentUserKey:
            friends1 = yield getFriends(parentUserKey, count=INFINITY)
            commonFriends = friends.intersection(friends1)
            keys.update(commonFriends)
        else:
            keys.update(friends)
    if acl in ["company", "public"]:
        companyKey = yield getCompanyKey(userKey)
        followers = yield getFollowers(userKey, count=INFINITY)
        keys.update(followers)
        keys.update(set([companyKey]))
    defer.returnValue(keys)


def checkAcl(userKey, acl, owner, friends=None, subscriptions=None,
            userCompKey=None, ownerCompKey=None):

    if acl == "public":
        return True
    if acl == "company":
        return (ownerCompKey and userCompKey) and ownerCompKey == userCompKey
    if acl in ["friends"]:
        if userKey == owner:
            return True
        else:
            return owner in friends if friends else False


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


def userName(id, user, classes=None):
    return "<span class='user %s'>" % (classes if classes else "") +\
           "<a class='ajax' href='/profile?id=%s'>%s</a></span>"\
           % (id, user["basic"]["name"])


def userAvatar(id, userInfo, size=None):
    size = size[0] if (size and len(size) != 0) else "m"
    avatar = userInfo.get("basic", {}).get("avatar", None)
    if avatar:
        imgType, itemId = avatar.split(":")
        return "/avatar/%s_%s.%s" % (size, itemId, imgType)

    return None


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
