
from twisted.web            import resource, server
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
        authinfo = request.getSession(IAuthInfo)
        currentuser = authinfo.username

        if len(request.postpath) == 3 and request.postpath[1] == 'u':
            userkey = "/".join(request.postpath)
        else:
            userkey = currentuser;

        d1 = defer.maybeDeferred(getUserRelation, currentuser, userkey)
        d2 = Db.get_slice(userkey, "users")
        dl = defer.DeferredList([d1, d2], 0, 1, 1)

        def callback(results):
            if not results[0][0] or not results[1][0]:
                return error.InternalServerError();

            userinfo = utils.supercolumnsToDict(results[1][1])
            args = {"relation": results[0][1], "userinfo": userinfo,
                    "userkey": userkey, "currentuser": currentuser}

            if not self.isAjax:
                render(request, "profile.mako", **args)
            else:
                renderDef(request, "profile.mako", "userProfileBlock", **args)

        dl.addCallback(callback)
        return server.NOT_DONE_YET
