
from twisted.web            import resource, server, http
from twisted.python         import log
from twisted.internet       import defer

from social.template        import render, renderDef
from social.relations       import UserRelation, getUserRelation, RELATION_SELF
from social.auth            import IAuthInfo
from social                 import Db, utils


class ProfileResource(resource.Resource):
    isLeaf = True
    isAjax = False
    def __init__(self, isAjax=False):
        self.isAjax = isAjax

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
        currentuser = authinfo.username

        if len(request.postpath) == 3 and request.postpath[1] == 'u':
            userkey = "/".join(request.postpath)
        elif len(request.postpath) != 0:
            request.redirect("/profile")
            request.finish()
            return
        else:
            userkey = currentuser

        # Get the relation with logged in user and the user information
        d1 = Db.get_slice(userkey, "users")
        d2 = defer.maybeDeferred(getUserRelation, currentuser, userkey)

        userinfoCol = yield d1
        userinfo = utils.supercolumnsToDict(userinfoCol)
        relation = yield d2
        detail = request.args['d'][0] if request.args.has_key('d') else 'notes'

        args = {"relation": relation, "userinfo": userinfo,
                "userkey": userkey, "currentuser": currentuser,
                "detail": detail}

        # Send the first block: Summary
        if self.isAjax:
            yield renderDef(request, "profile.mako", "summary", **args)
            yield renderDef(request, "profile.mako", "tabs", **args)
            yield renderDef(request, "profile.mako", "content", **args)

        if self.isAjax:
            request.finish()

        # This is not an ajax request, render the whole page!
        if not self.isAjax:
            yield render(request, "profile.mako", **args)
