import time
import uuid

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social             import Db, base, utils, errors
from social.isocial     import IAuthInfo
from social.isocial     import IItemType
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import dump_args, profile


class Activity(object):
    implements(IPlugin, IItemType)
    itemType = "activity"
    position = -1
    hasIndex = False


    def shareBlockProvider(self):
        raise errors.InvalidRequest()


    def rootHTML(self, convId, args):
        if "convId" in args:
            return getBlock("item.mako", "renderStatus", **args)
        else:
            return getBlock("item.mako", "renderStatus", args=[convId], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def renderRoot(self, request, convId, args):
        script = args['script']
        landing = not args['ajax']
        toFeed = args['toFeed'] if args.has_key('toFeed') else False
        if script:
            if not toFeed:
                yield renderScriptBlock(request, "item.mako", "conv_root",
                                        landing, "#conv-root-%s" %(convId),
                                        "set", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request):
        raise errors.InvalidRequest()


    def getResource(self, isAjax):
        return None


activity = Activity()
