
import hashlib
from social import Db


def md5(text):
    m = hashlib.md5()
    m.update(text)
    return m.hexdigest()

def monthName(num, long=False):
    short = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
             'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    full = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December']
    return full[num-1] if long else short[num-1]

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
        retval[item.name] = item.value
    return retval
