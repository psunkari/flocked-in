
from email.utils            import formatdate

from twisted.web            import resource, server
from twisted.internet       import defer
from twisted.python         import log

from social                 import Db, utils, base, plugins
from social.template        import render
from social.profile         import ProfileResource
from social.isocial         import IAuthInfo
from social.feed            import FeedResource
from social.register        import RegisterResource
from social.item            import ItemResource
from social.people          import PeopleResource
from social.avatar          import AvatarResource
from social.notifications   import NotificationsResource


def getPluggedResources(ajax=False):
    resources = {}
    for itemType in plugins:
        plugin = plugins[itemType]
        resource = plugin.getResource(ajax)
        if resource:
            resources[itemType] = resource

    return resources


class RootResource(resource.Resource):
    def __init__(self, isAjax=False):
        self._isAjax = isAjax
        self._initResources()

    def _initResources(self):
        self._feed = FeedResource(self._isAjax)
        self._profile = ProfileResource(self._isAjax)
        self._register = RegisterResource(self._isAjax)
        self._item = ItemResource(self._isAjax)
        self._people = PeopleResource(self._isAjax)
        self._notifications = NotificationsResource(self._isAjax)
        self._pluginResources = getPluggedResources(self._isAjax)
        if not self._isAjax:
            self._ajax = RootResource(True)
            self._avatars = AvatarResource()

    def getChildWithDefault(self, path, request):
        match = None
        if path == "" or path == "feed":
            match = self._feed
        elif path == "profile":
            match = self._profile
        elif path == "ajax" and not self._isAjax:
            match = self._ajax
        elif path == "register":
            match = self._register
        elif path == "item":
            match = self._item
        elif path == "people":
            match = self._people
        elif path == "avatar" and not self._isAjax:
            match = self._avatars
        elif path == "notifications":
            match = self._notifications
        elif path == "events":
            if "event" in plugins and self._pluginResources.has_key("event"):
                match = self._pluginResources["event"]
        elif path in plugins and self._pluginResources.has_key(path):
            match = self._pluginResources[path]

        if match and not self._isAjax:
            # By default prevent caching.
            # Any resource may change these headers later during the processing
            request.setHeader('Expires', formatdate(0))
            request.setHeader('Cache-control', 'private,no-cache,no-store,must-revalidate')

            # Also, add a cookie to indicate the page
            if request.method == "GET":
                cookiePath = None
                if path != "ajax":
                    cookiePath = path or "feed"
                elif "_fp" in request.args:
                    cookiePath = request.postpath[0]

                if cookiePath:
                    request.addCookie("_page", cookiePath, "/")

        return match or resource.NoResource("Page not found")
