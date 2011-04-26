
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

from social                 import _, __, Db, utils
from social.base            import BaseResource
from social.template        import getBlock
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

        # Fetch list of containers that I belong to and names
        # that match the given term
        d1 = Db.get_slice(userId, "userGroups")
        d2 = Db.get_slice(orgId, "nameIndex",
                          start=term, finish=finish, count=10)

        tagContainers = [orgId] if orgId else []
        toFetchEntities = set()
        users = []

        # Various containers that I belong to
        cols = yield d1
        for col in cols:
            gid = col.column.name
            tagContainers.append(gid)
            toFetchEntities.add(gid)

        # Fetch tags only from the containers that I belong to
        d3 = defer.succeed({}) if not tagContainers \
             else Db.multiget_slice(tagContainers, "orgTagsByName",
                                    start=term, finish=finish, count=10)

        # List of users that match the given term
        matchedUsers = yield d2
        for user in matchedUsers:
            name, uid = user.column.name.rsplit(':')
            users.append(uid)
            toFetchEntities.add(uid)

        # List of tags that match the given term
        tags = []
        matchedTags = yield d3
        for container, matches in matchedTags.items():
            toFetchEntities.add(container)
            for match in matches:
                tags.append({"title": match.column.name,
                             "id": match.column.value, "org": container})
        tags.sort(key=itemgetter("title"))

        # Fetch the required entities
        entities = {}
        if toFetchEntities:
            results = yield Db.multiget(toFetchEntities, "entities", "basic")
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
                    "meta": entities[tag["org"]]["basic"]["name"]}
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

        tagContainers = set([orgId]) if orgId else set()
        toFetchTags = set()

        # 1. Fetch item and get the list of tag containers (groups & orgs)
        # 2. See if I belong to any of those containers
        d1 = Db.get_slice(itemId, "items", super_column="meta")
        d2 = Db.get_slice(userId, "userGroups")

        cols = yield d1
        meta = utils.columnsToDict(cols)
        if "parent" in meta:    # This is a comment! Tags cannot exist here!!
            request.write("[]")
            return

        acl = meta.get("acl", {"accept": {"orgs":[orgId]}} if orgId else {})
        if not acl:     # No acl on item and user is external
            request.write("[]")
            return

        acl = pickle.loads(acl)
        accept = acl.get("accept", {})
        containersInACL = set(accept.get("orgs"))
        containersInACL.update(accept.get("groups", []))

        cols = yield d2
        tagContainers.update([x.column.name for x in cols])

        containers = containersInACL.intersection(tagContainers)

        # 3. Get list of tags from these containers that match the criteria
        d3 = defer.succeed({}) if not containers \
             else Db.multiget_slice(containers, "orgTagsByName",
                                    start=term, finish=finish, count=10)
        tags = []
        toFetchEntities = set()
        matchedTags = yield d3
        for container, matches in matchedTags.items():
            toFetchEntities.add(container)
            for match in matches:
                tags.append({"title": match.column.name,
                             "id": match.column.value, "org": container})
        tags.sort(key=itemgetter("title"))

        entities = {}
        if toFetchEntities:
            results = yield Db.multiget_slice(toFetchEntities, "entities",
                        ["name", "allowExternalUsers"], super_column="basic")
            entities.update(utils.multiColumnsToDict(results))

        output = []
        template = self._singleLineTemplate
        for tag in tags:
            title = tag["title"]
            data = {"title": title,
                    "meta": entities[tag["org"]]["name"]}
            output.append({"value": title,
                           "label": template%data,
                           "href": "/tags?id=%s"%tag["id"]})

        request.write(json.dumps(output))


    @defer.inlineCallbacks
    def _users(self, request, term, myFriendsOnly=False):
        pass


    @defer.inlineCallbacks
    def _groups(self, request, term, myGroupsOnly=False):
        pass


    @defer.inlineCallbacks
    def _myGroups(self, request):
        myId = request.getSession(IAuthInfo).username
        cols = yield Db.get_slice(myId, "userGroups")
        groupIds = [x.column.name for x in cols]

        groups = {}
        if groupIds:
            results = yield Db.multiget_slice(groupIds, "entities",
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
        term = utils.getRequestArg(request, "term")

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
