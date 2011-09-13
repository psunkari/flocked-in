import time
import ConfigParser
from functools          import wraps

from twisted            import python
from twisted.internet   import defer
from twisted.web.http   import Request

from social             import config

LOG_LEVELS = {'DEBUG': 10,
              'INFO': 20,
              'WARNING': 30,
              'WARN': 30,
              'ERROR': 40,
              'CRITICAL': '50' }

class logObserver(python.log.FileLogObserver):

    def __init__(self, f):

        defaultLogLevel = 'INFO'
        self.logLevel = defaultLogLevel
        try:
            self.logLevel = config.get('LOGGING', 'LOGLEVEL')
            if self.logLevel not in LOG_LEVELS:
                self.logLevel = defaultLogLevel
        except ConfigParser.NoSectionError:
            pass
        except ConfigParser.NoOptionError:
            pass

        self.logLevel = LOG_LEVELS[self.logLevel]
        python.log.FileLogObserver.__init__(self, f)

    def emit(self, eventDict):
        if 'logLevel' in eventDict:
            msgLogLevel = eventDict['logLevel']
        else:
            msgLogLevel = LOG_LEVELS['INFO']
        if msgLogLevel>= self.logLevel:
            python.log.FileLogObserver.emit(self, eventDict)


class logger(object):

    def debug(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['DEBUG']
        python.log.msg(*message, **kw)

    def info(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['INFO']
        python.log.msg(*message, **kw)

    def warn(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['WARN']
        python.log.msg(*message, **kw)

    def warning(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['WARNING']
        python.log.msg(*message, **kw)

    def error(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['ERROR']
        python.log.err(*message, **kw)

    def err(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['ERROR']
        python.log.err(*message, **kw)

    def critical(self, *message, **kw):
        kw['logLevel'] = LOG_LEVELS['CRITICAL']
        python.log.msg(*message, **kw)

    def msg(self, *message, **kw):
        self.critical("log.msg is DEPRECATE. use log.info")
        self.info(*message, **kw)


log = logger()

def dump_args(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        fname = func.__name__
        profiler_start = time.time()
        """
        allArgs = []

        argnames = func.func_code.co_varnames[:func.func_code.co_argcount]
        _allArgs = zip(argnames,args) + kwargs.items()

        for argName, value in _allArgs:
            if isinstance(value,  Request):
                allArgs.append((argName, value.args))
                log.debug(fname, "POSTPATH", value.postpath)
            else:
                allArgs.append((argName, value))
        argStr = ', '.join('%s=%r' % entry for entry in allArgs)
        log.debug(fname, "arguments", argStr)
        """
        ret = func(*args, **kwargs)
        """
        log.debug(fname, "dump_args","ReturnValue",ret)
        """
        log.info(fname, "dump_args", "ExecutionTime:", time.time()-profiler_start)
        return ret
    return wrapper


def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        fname = func.__name__
        profiler_start = time.time()
        def logReturnValue(retVal):
            """
            log.debug(fname, "ReturnValue",retVal)
            """
            log.info(fname, "ExecutionTime:", time.time()-profiler_start)
            return retVal
        ret = func(*args, **kwargs)
        if isinstance(ret, defer.Deferred) or \
           isinstance(ret, defer.DeferredList) or \
           isinstance(ret, defer.DeferredQueue):
            ret.addCallback(logReturnValue)
        else:
            logReturnValue(ret)
        return ret
    return wrapper
