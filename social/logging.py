import time
from functools          import wraps
from twisted.python     import log
from twisted.internet   import defer
from twisted.web.http   import Request

def dump_args(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        fname = func.__name__
        profiler_start = time.time()
        allArgs = []

        argnames = func.func_code.co_varnames[:func.func_code.co_argcount]
        _allArgs = zip(argnames,args) + kwargs.items()

        for argName, value in _allArgs:
            if isinstance(value,  Request):
                allArgs.append((argName, value.args))
                log.msg(fname, "POSTPATH", value.postpath)
            else:
                allArgs.append((argName, value))
        argStr = ', '.join('%s=%r' % entry for entry in allArgs)
        log.msg(fname, "arguments", argStr)
        ret = func(*args, **kwargs)
        log.msg(fname, "dump_args","ReturnValue",ret)
        log.msg(fname, "dump_args", "ExecutionTime:", time.time()-profiler_start)
        return ret
    return wrapper


def profile(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        fname = func.__name__
        profiler_start = time.time()
        def logReturnValue(retVal):
                log.msg(fname, "ReturnValue",retVal)
                log.msg(fname, "ExecutionTime:", time.time()-profiler_start)
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
