
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
    def __init__(self):
        self._feed = FeedResource()
        self._ajax = AjaxResource()
        self._profile = ProfileResource()
        self._register = RegisterResource()
        self._item = ItemResource()
        self._people = PeopleResource()
        self._avatars = AvatarResource()
        self._notifications = NotificationsResource()
        self.pluginResources = getPluggedResources(False)

    def getChildWithDefault(self, path, request):
        # By default prevent caching.
        # Any resource may change these headers later during the processing
        request.setHeader('Expires', formatdate(0))
        request.setHeader('Cache-control', 'private,no-cache,no-store,must-revalidate')

        if path == "" or path == "feed":
            return self._feed
        elif path == "profile":
            return self._profile
        elif path == "ajax":
            return self._ajax
        elif path == "register":
            return self._register
        elif path == "item":
            return self._item
        elif path == "people":
            return self._people
        elif path == "avatar":
            return self._avatars
        elif path == "notifications":
            return self._notifications
        elif path in plugins and self.pluginResources.has_key(path):
            return self.pluginResources[path]
        else:
            return resource.NoResource("Page not found")


class AjaxResource(RootResource):
    def __init__(self):
        self._feed = FeedResource(True)
        self._ajax = resource.NoResource("Page not found")
        self._avatars = resource.NoResource("Page not found")
        self._profile = ProfileResource(True)
        self._register = RegisterResource(True)
        self._item = ItemResource(True)
        self._people = PeopleResource(True)
        self.pluginResources = getPluggedResources(True)
        self._notifications = NotificationsResource(True)
