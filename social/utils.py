
import uuid
import hashlib
import datetime
import base64

from twisted.internet   import defer
from twisted.python     import log

from social             import Db, _, __

def md5(text):
    m = hashlib.md5()
    m.update(text)
    return m.hexdigest()


def toUserKey(id):
    user, domain = id.split("@")
    return domain + '/u/' + user


def supercolumnsToDict(supercolumns):
    retval = {}
    for item in supercolumns:
        name = item.super_column.name
        retval[name] = {}
        for col in item.super_column.columns:
            retval[name][col.name] = col.value
    return retval


def columnsToDict(columns):
    retval = {}
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
    encodedKey = getRequestArg(request, arg)
    try:
        userKey = decodeKey(encodedKey)
        col = yield Db.get(userKey, "userAuth", "passwordHash")
        defer.returnValue(userKey)
    except TypeError:
        raise errors.MissingParam()
    except Exception, e:
        log.err(e)
        raise errors.InvalidUser()


def areFriendlyDomains(one, two):
    domainOne = one.split("/", 1)[0]
    domainTwo = two.split("/", 1)[0]

    if domainOne != domainTwo:
        return False
    else:
        return True

def createACL(request):
    return None


def getRandomKey(prefix):
    key = prefix + "/" + str(uuid.uuid1())
    sha = hashlib.sha1()
    sha.update(key)
    return sha.hexdigest()


def encodeKey(key):
    return "xX" + base64.b64encode(key).strip('=')


def decodeKey(key):
    if not key.startswith("xX"):
        return key

    length = len(key) - 2
    return base64.b64decode(key[2:] + ((length % 4) * '='))


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
