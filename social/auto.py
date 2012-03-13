
import json
from operator               import itemgetter

from twisted.internet       import defer
from twisted.web            import resource, http

from social                 import db, utils, base
from social.isocial         import IAuthInfo
from social.logging         import log


def _getFinishTerm(term):
    finish = unicode(term, 'utf-8')
    finish = unicode(finish[:-1]) + unichr(ord(finish[-1]) + 1)
    return finish.encode('utf-8')


class AutoCompleteResource(base.BaseResource):
    isLeaf = True
    _template = "<div><div class='ui-ac-icon'><img src='%(icon)s'/></div>" +\
                "<div class='ui-ac-title'>%(title)s</div>" +\
                "<div class='ui-ac-meta'>%(meta)s</div></div>"
    _singleLineTemplate = "<div><span class='ui-ac-title2'>%(title)s</span>" +\
                          "<span class='ui-ac-meta2'>%(meta)s</span></div>"
    _dlgLinetemplate = """
      <div class="ui-listitem">
        <div class="ui-list-icon"><img src='%(icon)s'/></div>
        <div class="ui-list-title">%(title)s</div>
        <div class="ui-list-meta">%(meta)s</div>
        <div class="ui-list-action"></div>
      </div>
    """

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

        orgId = request.getSession(IAuthInfo).organization
        finish = _getFinishTerm(term)

        # Fetch list of tags and names that match the given term
        d1 = db.get_slice(orgId, "orgTagsByName",
                          start=term, finish=finish, count=10)
        d2 = db.get_slice(orgId, "nameIndex",
                          start=term, finish=finish, count=10)
        d3 = db.get_slice(orgId, "entityGroupsMap",
                          start=term, finish=finish, count=10)

        toFetchEntities = set()
        users = []
        groups = []

        # List of users that match the given term
        matchedUsers = yield d2
        for user in matchedUsers:
            name, uid = user.column.name.rsplit(':')
            if uid not in toFetchEntities:
                users.append(uid)
                toFetchEntities.add(uid)

        matchedGroup = yield d3
        for group in matchedGroup:
            name, groupId = group.column.name.split(':')
            if groupId not in toFetchEntities:
                groups.append(groupId)
                toFetchEntities.add(groupId)

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
            entities = base.EntitySet(toFetchEntities)
            yield entities.fetchData()

        output = []
        template = self._template
        avatar = utils.userAvatar
        groupAvatar = utils.groupAvatar

        for uid in users:
            if uid in entities:
                name = entities[uid].basic["name"]
                data = {"icon": avatar(uid, entities[uid], "s"), "title": name,
                        "meta": entities[uid].basic.get("jobTitle", "")}
                output.append({"value": name,
                               "label": template % data,
                               "href": "/profile?id=%s" % uid})

        for groupId in groups:
            if groupId in entities:
                name = entities[groupId].basic['name']
                data = {"icon": groupAvatar(groupId, entities[groupId], "s"),
                        "title": name, 'meta': '&nbsp;'}
                output.append({"value": name,
                               "label": template % data,
                               "href": "/group?id=%s" % groupId})

        for tag in tags:
            title = tag["title"]
            data = {"icon": "/rsrcs/img/tag-small.png", "title": title,
                    "meta": '&nbsp;'}
            output.append({"value": title,
                           "label": template % data,
                           "href": "/tags?id=%s" % tag["id"]})

        request.write(json.dumps(output))

    @defer.inlineCallbacks
    def _tags(self, request, term):
        if len(term) < 2:
            request.write("[]")
            return
        orgId = request.getSession(IAuthInfo).organization
        finish = _getFinishTerm(term)
        itemId = utils.getRequestArg(request, "itemId")
        if not itemId:
            request.write("[]")
            return

        toFetchTags = set()

        d1 = db.get_slice(orgId, "orgTagsByName", start=term,
                          finish=finish, count=10)
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
            data = {"title": tag['title'], "meta": ''}
            output.append({"value": tag['title'],
                           "label": template % data,
                           "href": "/tags?id=%s" % tag["id"]})

        request.write(json.dumps(output))

    @defer.inlineCallbacks
    def _users(self, request, term):
        if len(term) < 2:
            request.write("[]")
            return

        orgId = request.getSession(IAuthInfo).organization
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
            entities = base.EntitySet(toFetchEntities)
            yield entities.fetchData()

        output = []
        template = self._template
        avatar = utils.userAvatar

        for uid in users:
            if uid in entities:
                name = entities[uid].basic["name"]
                data = {"icon": avatar(uid, entities[uid], "s"), "title": name,
                        "meta": entities[uid].basic.get("jobTitle", "")}
                output.append({"value": name, "uid": uid,
                               "label": template % data})

        request.write(json.dumps(output))

    @defer.inlineCallbacks
    def _groups(self, request, term):
        pass

    @defer.inlineCallbacks
    def _myGroups(self, request):
        myId = request.getSession(IAuthInfo).username
        cols = yield db.get_slice(myId, "entityGroupsMap")
        groupIds = [x.column.name.split(':', 1)[1] for x in cols]

        groups = {}
        if groupIds:
            groups = base.EntitySet(groupIds)
            yield groups.fetchData()

        output = []
        for id in groupIds:
            obj = {"id": id, "name": groups[id].basic["name"],
                   "external": True if groups[id].basic.get("allowExternalusers", "closed") == "open" else False}
            output.append(obj)

        request.write(json.dumps(output))

    @defer.inlineCallbacks
    def _myCollection(self, request, term):
        authInfo = request.getSession(IAuthInfo)
        myId = authInfo.username
        orgId = authInfo.organization
        finish = _getFinishTerm(term)

        # Fetch list of tags and names that match the given term
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

        # Fetch the required entities
        entities = {}
        if toFetchEntities:
            entities = base.EntitySet(toFetchEntities)
            yield entities.fetchData()

        output = []
        template = self._dlgLinetemplate
        avatar = utils.userAvatar

        for uid in users:
            if uid in entities:
                name = entities[uid].basic["name"]
                data = {"icon": avatar(uid, entities[uid], "s"), "title": name,
                        "meta": entities[uid].basic.get("jobTitle", "")}
                output.append({"label": template % data,
                               "type": "user",
                               "value": uid})

        cols = yield db.get_slice(myId, "entityGroupsMap", start=term.lower(),
                                  finish=finish.lower(), count=10)
        groupIds = [x.column.name.split(':', 1)[1] for x in cols]
        avatar = utils.groupAvatar
        groups = {}

        if groupIds:
            groups = base.EntitySet(groupIds)
            yield groups.fetchData()

        for groupId in groupIds:
            data = {"icon": avatar(groupId, groups[groupId], "s"),
                    "title": groups[groupId].basic["name"],
                    "meta": groups[groupId].basic.get("desc", "&nbsp;")}
            obj = {"value": groupId, "label": template % data, "type": "group"}
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
        elif path == "groups":
            d = self._groups(request, term)
        elif path == "mygroups":
            d = self._myGroups(request)
        elif path == "mycollection":
            d = self._myCollection(request, term)

        return self._epilogue(request, d)
