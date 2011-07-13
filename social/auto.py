
import json
try:
    import cPickle as pickle
except:
    import pickle
from operator               import itemgetter

from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.python         import log
from twisted.web            import resource, server, http

from social                 import _, __, db, utils
from social.base            import BaseResource
from social.isocial         import IAuthInfo


def _getFinishTerm(term):
    finish = unicode(term, 'utf-8')
    finish = unicode(finish[:-1]) + unichr(ord(finish[-1]) + 1)
    return finish.encode('utf-8')


class AutoCompleteResource(BaseResource):
    isLeaf = True
    _template = "<div><div class='ui-ac-icon'><img src='%(icon)s'/></div>" +\
                "<div class='ui-ac-title'>%(title)s</div>" +\
                "<div class='ui-ac-meta'>%(meta)s</div></div>"
    _singleLineTemplate = "<div><span class='ui-ac-title'>%(title)s</span>" +\
                          "<span class='ui-ac-meta'>%(meta)s</span></div>"

    #
    # For the searchbox, we show the list of users, groups and tags
    # in the company.  When one of them is choosen, the user will be sent
    # to the profile page of the user/group or is shown the list of items.
    #
    @defer.inlineCallbacks
    def _searchbox(self, request, term):
        if len(term) < 3:
            request.write("[]")
            return

        authInfo = request.getSession(IAuthInfo)
        userId = authInfo.username
        orgId = authInfo.organization
        finish = _getFinishTerm(term)

        # Fetch list of tags and names that match the given term
        d1 = db.get_slice(orgId, "orgTagsByName",
                          start=term, finish=finish, count=10)
        d2 = db.get_slice(orgId, "nameIndex",
                          start=term, finish=finish, count=10)

        toFetchEntities = set()
        users = []

        # List of users that match the given term
        matchedUsers = yield d2
        for user in matchedUsers:
            name, uid = user.column.name.rsplit(':')
            if uid not in toFetchEntities:
                users.append(uid)
                toFetchEntities.add(uid)

        # List of tags that match the given term
        tags = []
        matchedTags = yield d1
        matchedTags = [match.column.value for match in matchedTags]
        if matchedTags:
            matchedTags = yield db.get_slice(orgId, "orgTags", matchedTags)
            matchedTags = utils.supercolumnsToDict(matchedTags)
            for tagId in matchedTags:
                tags.append({'title': matchedTags[tagId]['title'],
                             'id': tagId})
        tags.sort(key=itemgetter("title"))

        # Fetch the required entities
        entities = {}
        if toFetchEntities:
            results = yield db.multiget(toFetchEntities, "entities", "basic")
            entities.update(utils.multiSuperColumnsToDict(results))

        output = []
        template = self._template
        avatar = utils.userAvatar

        for uid in users:
            if uid in entities:
                name = entities[uid]["basic"]["name"]
                data = {"icon": avatar(uid, entities[uid], "s"), "title": name,
                        "meta": entities[uid]["basic"].get("jobTitle", "")}
                output.append({"value": name,
                               "label": template%data,
                               "href": "/profile?id=%s"%uid})

        for tag in tags:
            title = tag["title"]
            data = {"icon": "", "title": title,
                    "meta": ''}
            output.append({"value": title,
                           "label": template%data,
                           "href": "/tags?id=%s"%tag["id"]})

        request.write(json.dumps(output))


    @defer.inlineCallbacks
    def _tags(self, request, term):
        if len(term) < 2:
            request.write("[]")
            return
        authInfo = request.getSession(IAuthInfo)
        userId = authInfo.username
        orgId = authInfo.organization
        finish = _getFinishTerm(term)
        itemId = utils.getRequestArg(request, "itemId")
        if not itemId:
            request.write("[]")
            return

        toFetchTags = set()

        d1 = db.get_slice(orgId, "orgTagsByName",
                          start=term, finish=finish, count=10)
        tags = []
        matchedTags = yield d1
        matchedTags = [match.column.value for match in matchedTags]
        if matchedTags:
            matchedTags = yield db.get_slice(orgId, "orgTags", matchedTags)
            matchedTags = utils.supercolumnsToDict(matchedTags)
            for tagId in matchedTags:
                tags.append({'title': matchedTags[tagId]['title'],
                             'id': tagId})
        tags.sort(key=itemgetter("title"))

        output = []
        template = self._singleLineTemplate
        for tag in tags:
            title = tag["title"]
            data = {"title": title,
                    "meta": ''}
            output.append({"value": title,
                           "label": template%data,
                           "href": "/tags?id=%s"%tag["id"]})

        request.write(json.dumps(output))


    @defer.inlineCallbacks
    def _users(self, request, term, myFriendsOnly=False):
        if len(term) < 2:
            request.write("[]")
            return

        authInfo = request.getSession(IAuthInfo)
        userId = authInfo.username
        orgId = authInfo.organization
        finish = _getFinishTerm(term)

        # List of matching names in the company
        d1 = db.get_slice(orgId, "nameIndex",
                          start=term, finish=finish, count=5)

        toFetchEntities = set()
        users = []

        # List of users that match the given term
        matchedUsers = yield d1
        for user in matchedUsers:
            name, uid = user.column.name.rsplit(':')
            if uid not in toFetchEntities:
                users.append(uid)
                toFetchEntities.add(uid)

        # Fetch the required entities
        entities = {}
        if toFetchEntities:
            results = yield db.multiget(toFetchEntities, "entities", "basic")
            entities.update(utils.multiSuperColumnsToDict(results))

        output = []
        template = self._template
        avatar = utils.userAvatar

        for uid in users:
            if uid in entities:
                name = entities[uid]["basic"]["name"]
                data = {"icon": avatar(uid, entities[uid], "s"), "title": name,
                        "meta": entities[uid]["basic"].get("jobTitle", "")}
                output.append({"value": name, "uid":uid,
                               "label": template%data})

        request.write(json.dumps(output))


    @defer.inlineCallbacks
    def _groups(self, request, term):
        pass


    @defer.inlineCallbacks
    def _myGroups(self, request):
        myId = request.getSession(IAuthInfo).username
        cols = yield db.get_slice(myId, "entityGroupsMap")
        groupIds = [x.column.name for x in cols]

        groups = {}
        if groupIds:
            results = yield db.multiget_slice(groupIds, "entities",
                        ["name", "allowExternalUsers"], super_column="basic")
            groups.update(utils.multiColumnsToDict(results))

        output = []
        for id in groupIds:
            obj = {"id": id, "name": groups[id]["name"],
                   "external": True if groups[id].get("allowExternalusers", "closed") == "open" else False}
            output.append(obj)

        request.write(json.dumps(output))


    def render_GET(self, request):
        if len(request.postpath) == 0:
            return resource.ErrorPage(404, http.RESPONSES[404],
                                      "Resource not found")

        path = request.postpath[0]
        term = utils.getRequestArg(request, "term") or ''
        term = term.lower()

        d = None
        if path == "searchbox":
            d = self._searchbox(request, term)
        elif path == "tags":
            d = self._tags(request, term)
        elif path == "users":
            d = self._users(request, term)
        elif path == "friends":
            d = self._users(request, term, True)
        elif path == "groups":
            d = self._groups(request, term)
        elif path == "mygroups":
            d = self._myGroups(request)

        return self._epilogue(request, d)
