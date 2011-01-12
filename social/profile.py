
from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer
from telephus.cassandra     import ttypes

from social.template        import render, renderDef
from social.relations       import Relation
from social.auth            import IAuthInfo
from social                 import Db, utils


class ProfileResource(resource.Resource):
    isLeaf = True
    isAjax = False
    def __init__(self, isAjax=False):
        self.isAjax = isAjax

    def _default(self):
        request.redirect("/profile")
        request.finish()

    @defer.inlineCallbacks
    def _connect(self, request):
        if not request.args.has_key("target"):
            self._default()
            return

        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username
        targetKey = request.args["target"][0]

        (myDomain, ign, myId) = myKey.partition("/u/")
        (targetDomain, ign, targetId) = targetKey.partition("/u/")

        # TODO: In future support friendly domains
        # to allow the network span across multiple domains
        if myDomain != targetDomain:
            self._default()
            return

        try:
            result = yield Db.get(myKey, "connections", targetKey)
            if result.column.value == "__local__":
                d1 = Db.insert(myKey, "connections", "", targetKey)
                d2 = Db.insert(targetKey, "connections", "", myKey)
                yield d1
                yield d2
        except ttypes.NotFoundException:
            d1 = Db.insert(myKey, "connections", "__remote__", targetKey)
            d2 = Db.insert(targetKey, "connections", "__local__", myKey)
            yield d1
            yield d2

    def render_POST(self, request):
        done = False
        if len(request.postpath) == 1:
            action = request.postpath[0]
            if action == "connect":
                self._connect(request)
                return server.NOT_DONE_YET

        self._default()

    def render_GET(self, request):
        d = self._render(request)
        def errback(err):
            log.err(err)
            request.setResponseCode(500)
            request.finish()
        d.addErrback(errback)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _render(self, request):
        authinfo = request.getSession(IAuthInfo)
        myKey = authinfo.username

        if len(request.postpath) == 3 and request.postpath[1] == 'u':
            userKey = "/".join(request.postpath)
        elif len(request.postpath) != 0:
            request.redirect("/profile")
            request.finish()
            return
        else:
            userKey = myKey

        # Get the user's profile information
        cols = yield Db.multiget_slice([myKey, userKey], "users")

        relation = Relation(myKey, userKey)
        userInfo = utils.supercolumnsToDict(cols[userKey])
        myInfo = utils.supercolumnsToDict(cols[myKey])
        detail = request.args['d'][0] if request.args.has_key('d') else 'notes'

        args = {"relation": relation, "user": userInfo, "me": myInfo,
                "userKey": userKey, "myKey": myKey, "detail": detail}

        # Send the first block: Summary
        if self.isAjax:
            yield relation.isFriend()
            yield renderDef(request, "profile.mako", "summary", **args)
            yield renderDef(request, "profile.mako", "tabs", **args)
            yield renderDef(request, "profile.mako", "content", **args)

        if self.isAjax:
            request.finish()

        # This is not an ajax request, render the whole page!
        if not self.isAjax:
            yield render(request, "profile.mako", **args)
