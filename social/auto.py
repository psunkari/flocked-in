
import json
from operator               import itemgetter

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

    #
    # For the searchbox, we show the list of users, groups and tags
    # in the company.  When one of them is choosen, the user will be sent
    # to the profile page or the user/group or shown the list of items.
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
        d1 = Db.get_slice(userId, "userGroups", count=10)
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
                output.append({"value": _("User: %s")%name,
                               "label": template%data,
                               "href": "/profile?id=%s"%uid})

        for tag in tags:
            title = tag["title"]
            data = {"icon": "", "title": title,
                    "meta": entities[tag["org"]]["basic"]["name"]}
            output.append({"value": _("Tag: %s")%title,
                           "label": template%data,
                           "href": "/tags?id=%s"%tag["id"]})

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

        return self._epilogue(request, d)
