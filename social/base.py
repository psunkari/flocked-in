
import json
import urlparse
import regex
from functools              import wraps
from itertools              import ifilter

from twisted.web            import resource, server, http
from twisted.internet       import defer

from social                 import db, utils, errors
from social                 import template as t
from social.isocial         import IAuthInfo
from social.logging         import log


class RESTfulResource(resource.Resource):
    """Simple wrapper over resource.Resource to make
    handling RESTful APIs easier
    Based on txrestapi: https://github.com/iancmcc/txrestapi
    """
    _registry = None

    def __init__(self):
        self._registry = []
        self._registerPaths()

    def _registerPaths(self, paths=None):
        """Register all paths given or all those returned by
        paths method of this object.
        """
        paths = paths if paths else self.paths()
        for (method, path, callback) in paths:
            self._registry.append((method, regex.compile(path), callback))

    def paths(self):
        """ Return list of static paths supported by this resource
        Classes inheriting from this class must override the paths
        function to specify static paths supported by this resource
        """
        return []

    def callback(self, request):
        """Fetch the first matching registered handler for the request.

        Keyword arguments:
        @request: Request whose path will be matched
        """
        filterf = lambda t: t[0] in (request.method, 'ALL')
        path = "/" + "/".join(request.postpath) if request.postpath else ''
        for m, r, cb in ifilter(filterf, self._registry):
            result = r.search(path)
            if result:
                return cb, result.groupdict()
        return None, None

    def register(self, method, path, callback):
        """Add a new path handler to the registry.

        Keyword arguments:
        @method: HTTP method
        @path: Regular expression to match for path
        @callback: Function to be called when a matching path is requested
        """
        self._registry.append((method, regex.compile(path), callback))

    def unregister(self, method, path, callback):
        """Remove the path handler from the registry.

        Keyword arguments:
        @method: HTTP method
        @path: Regular expression to match for path
        @callback: Function to be called when a matching path is requested
        """
        if path is not None:
            path = regex.compile(path)

        for m, r, cb in self._registry[:]:
            if not method or (method and m == method):
                if not path or (path and r == path):
                    if not callback or (callback and cb == callback):
                        self._registry.remove((m, r, cb))


class BaseResource(RESTfulResource):
    requireAuth = True
    _templates = ['signin.mako', 'errors.mako']
    _ajax = False

    def __init__(self, ajax=False):
        RESTfulResource.__init__(self)
        self._ajax = ajax
        t.warmupTemplateCache(self._templates)

    @defer.inlineCallbacks
    def _getBasicArgs(self, request):
        auth = yield defer.maybeDeferred(request.getSession, IAuthInfo)
        myId = auth.username
        orgId = auth.organization
        isOrgAdmin = auth.isAdmin

        script = False if '_ns' in request.args or\
                          request.getCookie('_ns') else True
        appchange = True if '_fp' in request.args and self._ajax or\
                            not self._ajax and script else False

        entities = EntitySet([myId, orgId])
        yield entities.fetchData()
        args = {"me": entities[myId], "isOrgAdmin": isOrgAdmin,
                "ajax": self._ajax, "script": script, "org": entities[orgId],
                "myId": myId, "orgId": orgId}

        if appchange:
            latest = yield utils.getLatestCounts(request, False)
            args["latest"] = latest

        defer.returnValue((appchange, script, args, myId))

    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
        try:
            failure.raiseException()
        except errors.BaseError, e:
            errorCode, errorBrief, shortErrorStr, fullErrorStr = e.errorData()
        except Exception, e:
            fullErrorStr = """<p>Something went wrong when processing your
                request.  The incident got noted and we are working on it.</p>
                <p>Please try again after sometime.</p>"""
            errorCode = 500
            shortErrorStr = """Oops... Unable to process your request.
                Please try after sometime"""

        log.err(failure)
        referer = request.getHeader('referer')
        try:
            appchange, script, args, myId = yield self._getBasicArgs(request)
            ajax = self._ajax
            args["referer"] = referer

            if ajax and not appchange:
                request.setResponseCode(errorCode)
                request.write(shortErrorStr)
            elif ajax and appchange:
                args["msg"] = fullErrorStr
                t.renderScriptBlock(request, "errors.mako", "layout",
                                    not ajax, "#mainbar", "set", **args)
            else:
                if referer:
                    fromNetLoc = urlparse.urlsplit(referer)[1]
                    myNetLoc = urlparse.urlsplit(request.uri)[1]
                    if fromNetLoc != myNetLoc:
                        args["isDeepLink"] = True
                else:
                    args["isDeepLink"] = True

                args["msg"] = fullErrorStr
                if script:
                    request.write("<script>$('body').empty();</script>")
                t.render(request, "errors.mako", **args)
        except Exception, e:
            args = {"msg": fullErrorStr}
            t.renderDef(request, "errors.mako", "fallback", **args)

    def _epilogue(self, request, deferred=None):
        d = deferred if deferred else defer.fail(errors.NotFoundError())

        def closeConnection(x=None):
            if not request._disconnected:
                request.finish()

        # Handle any errors that may have occurred before
        # closeing the connection.
        if not isinstance(d, defer.Deferred):
            closeConnection()
        else:
            d.addErrback(self._handleErrors, request)
            d.addBoth(closeConnection)

        return server.NOT_DONE_YET

    def render(self, request):
        callback, args = self.callback(request)
        if callback:
            deferred = defer.maybeDeferred(callback, request, **args)
            return self._epilogue(request, deferred)
        else:
            m = getattr(self, 'render_' + request.method, None)
            if m:
                return m(request)

        # We don't have a handler or a render method defined.
        # That means we must throw a 404 error!
        return self._epilogue(request, None)


class APIBaseResource(RESTfulResource):
    isLeaf = True

    def _ensureAccessScope(self, request, needed):
        token = request.apiAccessToken
        if not token:
            raise errors.PermissionDenied()

        if needed not in token.scope:
            raise errors.PermissionDenied()

        return token

    @defer.inlineCallbacks
    def _handleErrors(self, failure, request):
        try:
            failure.raiseException()
        except errors.BaseError, e:
            errorCode, errorBrief, shortErrorStr, fullErrorStr = e.errorData()
        except:
            errorCode = 500
            errorBrief = http.RESPONSES[500]

        log.err(failure)
        request.setResponseCode(errorCode, errorBrief)
        request.setHeader('content-type', 'application/json')
        responseObj = {'error': errorBrief, 'error_description': fullErrorStr}
        request.write(json.dumps(responseObj))

    def _epilogue(self, request, deferred=None):
        d = deferred if deferred else defer.fail(errors.NotFoundError())

        # Check for errors.
        d.addErrback(self._handleErrors, request)

        # Finally, close the connection if not already closed.
        def closeConnection(x):
            if not request._disconnected:
                request.finish()
        d.addBoth(closeConnection)
        return server.NOT_DONE_YET

    def _success(self, request, httpCode, responseObj):
        request.setResponseCode(httpCode, http.RESPONSES[httpCode])
        request.setHeader('content-type', 'application/json')
        request.write(json.dumps(responseObj))


class Entity(object):

    def __init__(self, entityId, data=None):
        self.id = entityId
        self._data = {} if not data else data

    @defer.inlineCallbacks
    def fetchData(self, columns=None):
        if columns == None:
            columns = ['basic']
        if columns == []:
            data = yield db.get_slice(self.id, "entities")
        else:
            data = yield db.get_slice(self.id, "entities", columns)
        data = utils.supercolumnsToDict(data)
        self._data = data

    def update(self, data):
        for supercolumn in data:
            if supercolumn not in self._data:
                self._data[supercolumn] = {}
            self._data[supercolumn].update(data[supercolumn])

    @defer.inlineCallbacks
    def save(self):
        yield db.batch_insert(self.id, 'entities', self._data)

    def __getattr__(self, name):
        return self._data.get(name, {})

    def __contains__(self, name):
        return name in self._data

    def keys(self):
        return self._data.keys()

    def has_key(self, name):
        return name in self._data

    def get(self, name, default=None):
        return self._data.get(name, default)

    def isEmpty(self):
        return self._data == {}


class EntitySet(object):
    def __init__(self, ids):
        if isinstance(ids, list) or isinstance(ids, set):
            self.ids = list(ids)
            self.data = {}
        elif isinstance(ids, dict):
            self.ids = ids.keys()
            self.data = ids
        elif isinstance(ids, Entity):
            entity = ids
            self.ids = [entity.id]
            self.data = {entity.id: entity}
        else:
            raise Exception('Invalid')

    @defer.inlineCallbacks
    def fetchData(self, columns=None):
        if not columns:
            columns = ['basic']
        entities = yield db.multiget_slice(self.ids, "entities", columns)
        entities = utils.multiSuperColumnsToDict(entities)
        for entityId in entities:
            entity = Entity(entityId, entities[entityId])
            self.data[entityId] = entity

    def __getitem__(self, entityId):
        return self.data[entityId]

    def __setitem__(self, entityId, entity):
        if entityId not in self.ids:
            self.ids.append(entityId)
        self.data[entityId] = entity

    def __delitem__(self, entityId):
        del self.data[entityId]
        self.ids.remove(entityId)

    def __contains__(self, entityId):
        return entityId in self.data

    def keys(self):
        return self.data.keys()

    def values(self):
        return self.data.values()

    def items(self):
        return self.data.items()

    def has_key(self, entityId):
        return entityId in self.data

    def get(self, entityId, default=None):
        return self.data.get(entityId, default)

    def update(self, values):
        if isinstance(values, dict):
            for eid in values:
                if eid not in self.ids:
                    self.ids.append(eid)
                self.data[eid] = values[eid]
        elif isinstance(values, Entity):
            if  values.id not in self.ids:
                self.ids.append(values.id)
            self.data[values.id] = values
