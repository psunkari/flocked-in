from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base, _
from social.relations   import Relation
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE
from social.logging     import dump_args, profile

@defer.inlineCallbacks
def getPeople(myId, entityId, orgId, start='',
              count=PEOPLE_PER_PAGE, fn=None):
    # dont list blocked users.
    # dont list deleted users.
    # always return list of names ordered by name.
    #

    cols = yield Db.get_slice(orgId, "blockedUsers")
    blockedUsers = utils.columnsToDict(cols).keys()
    toFetchCount = count + 1
    nextPageStart = None
    userIds = []

    if not fn:
        cols = yield Db.get_slice(entityId, "displayNameIndex",
                                  start=start, count=toFetchCount)
        userIds = [col.column.name.split(":")[1] for col in cols]
        if len(userIds) > count:
            nextPageStart = cols[-1].column.name
            userIds = userIds[0:count]
        toFetchUsers = userIds
    else:
        toFetchUsers, _nextPageStart = yield fn(entityId, start, toFetchCount)
        if len(toFetchUsers) < toFetchCount:
            nextPageStart = None
            userIds = toFetchUsers
        else:
            nextPageStart = _nextPageStart
            userIds = toFetchUsers[0:count]

    usersDeferred = Db.multiget_slice(toFetchUsers, "entities", ["basic"])
    relation = Relation(myId, userIds)
    results = yield defer.DeferredList([usersDeferred,
                                        relation.initFriendsList(),
                                        relation.initPendingList(),
                                        relation.initSubscriptionsList()])
    users = utils.multiSuperColumnsToDict(results[0][1])
    defer.returnValue((users, relation, userIds, blockedUsers, nextPageStart))


class PeopleResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request, viewType, start):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        orgId = args["orgKey"]
        start = utils.getRequestArg(request, "start") or ''
        args["entities"] = {}
        args["menuId"] = "people"

        if script and landing:
            yield render(request, "people.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        d = None
        if viewType == "all":
            d = getPeople(myId, orgId, orgId, start=start)
        elif viewType == "friends":
            d = getPeople(myId, myId, orgId, start=start, fn=self._getFriends)
        else:
            raise errors.InvalidRequest()

        users, relations, userIds, blockedUsers, nextPageStart = yield d

        # First result tuple contains the list of user objects.
        args["entities"] = users
        args["relations"] = relations
        args["people"] = userIds
        args["nextPageStart"] = nextPageStart
        args["viewType"] = viewType

        if script:
            yield renderScriptBlock(request, "people.mako", "viewOptions",
                                landing, "#people-view", "set", args=[viewType])
            yield renderScriptBlock(request, "people.mako", "listPeople",
                                    landing, "#users-wrapper", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)


    @defer.inlineCallbacks
    def _getFriends(self, userId, start, count=PEOPLE_PER_PAGE):
        log.msg("Getting friends")
        cols = yield Db.get_slice(userId, "connections")
        friends = [x.super_column.name for x in cols]

        cols = yield Db.get_slice(userId, "displayNameIndex", count=count)

        ret = []
        toFetchStart = start
        nextPageStart = None
        while len(ret) < count:
            cols = yield Db.get_slice(userId, "displayNameIndex",
                                  start=toFetchStart, count=count)
            if not cols:
                nextPageStart = None
                break
            toFetchStart = cols[-1].column.name
            for col in cols:
                userId = col.column.name.split(":")[1]
                if userId in friends:
                    ret.append(userId)
                if len(ret) == count:
                    nextPageStart = col.column.name

        defer.returnValue((ret, nextPageStart))


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            viewType = utils.getRequestArg(request, "type") or "friends"
            start = utils.getRequestArg(request, "start")
            d = self._render(request, viewType, start)

        return self._epilogue(request, d)
