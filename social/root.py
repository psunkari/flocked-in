
from twisted.web            import resource, server
from twisted.internet       import defer

from social                 import Db, utils, base
from social.template        import render
from social.profile         import ProfileResource
from social.auth            import IAuthInfo
from social.feed            import FeedResource


class RootResource(resource.Resource):
    def __init__(self):
        self._feed = FeedResource()
        self._ajax = AjaxResource()
        self._profile = ProfileResource()

    def getChildWithDefault(self, path, request):
        if path == "" or path == "feed":
            return self._feed
        elif path == "profile":
            return self._profile
        elif path == "ajax":
            return self._ajax
        else:
            return resource.NoResource("Page not found")


class AjaxResource(RootResource):
    def __init__(self):
        self._feed = FeedResource(True)
        self._ajax = resource.NoResource("Page not found")
        self._profile = ProfileResource(True)
