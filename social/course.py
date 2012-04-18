from twisted.internet   import defer
from telephus.cassandra import ttypes
from formencode         import compound

from social             import base, db, utils, errors, _, plugins
from social             import template as t
from social.core        import Feed
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args
from social.validators  import Validate, SocialSchema, Entity, SocialString
from social.core        import Group


class CourseResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _renderForum(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        args["menuId"] = "courses"
        args["filterType"] = "trending"

        if script and landing:
            t.render(request, "course.mako", **args)
        elif script and appchange:
            t.renderScriptBlock(request, "course.mako", "layout",
                                landing, "#mainbar", "set", **args)
        if script:
            onload = "$$.files.init('sharebar-attach');"

            #t.renderScriptBlock(request, "course.mako", "summary",
            #                    landing, "#group-summary", "set", **args)
            #t.renderScriptBlock(request, "feed.mako", "share_block",
            #                    landing,  "#share-block", "set",
            #                    handlers={"onload": onload}, **args)
            #yield self._renderShareBlock(request, "status")

        if script:
            onload = ""
            t.renderScriptBlock(request, "course.mako", "feed", landing,
                                "#user-feed-wrapper", "set", True,
                                handlers={"onload": onload}, **args)
        else:
            t.render(request, "course.mako", **args)

    @defer.inlineCallbacks
    def _renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderForum(request)

        return self._epilogue(request, d)

class CourseTopicResource(base.BaseResource):
    pass
