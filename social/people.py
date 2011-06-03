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
    cols = yield Db.get_slice(orgId, "blockedUsers")
    blockedUsers = utils.columnsToDict(cols).keys()
    toFetchCount = count + 1
    nextPageStart = None
    prevPageStart = None
    userIds = []

    if not fn:
        d1 = Db.get_slice(entityId, "displayNameIndex",
                          start=start, count=toFetchCount)
        d2 = Db.get_slice(entityId, "displayNameIndex",
                    start=start, count=toFetchCount, reverse=True)\
                    if start else None

        # Get the list of users (sorted by displayName)
        cols = yield d1
        userIds = [col.column.name.split(":")[1] for col in cols]
        if len(userIds) > count:
            nextPageStart = cols[-1].column.name
            userIds = userIds[0:count]
        toFetchUsers = userIds

        # Start of previous page
        if start and d2:
            prevCols = yield d2
            if prevCols and len(prevCols) > 1:
                prevPageStart = prevCols[-1].column.name
    else:
        userIds, nextPageStart, prevPageStart\
                                = yield fn(entityId, start, toFetchCount)
        toFetchUsers = userIds

    usersDeferred = Db.multiget_slice(toFetchUsers, "entities", ["basic"])
    relation = Relation(myId, userIds)
    results = yield defer.DeferredList([usersDeferred,
                                        relation.initFriendsList(),
                                        relation.initPendingList(),
                                        relation.initSubscriptionsList()])
    users = utils.multiSuperColumnsToDict(results[0][1])

    defer.returnValue((users, relation, userIds,\
                       blockedUsers, nextPageStart, prevPageStart))


class PeopleResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request, viewType, start):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        orgId = args["orgKey"]
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
            d = getPeople(myId, myId, orgId, start=start)
        else:
            raise errors.InvalidRequest()

        users, relations, userIds,\
            blockedUsers, nextPageStart, prevPageStart = yield d

        # First result tuple contains the list of user objects.
        args["entities"] = users
        args["relations"] = relations
        args["people"] = userIds
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["viewType"] = viewType

        if script:
            yield renderScriptBlock(request, "people.mako", "viewOptions",
                                landing, "#people-view", "set", args=[viewType])
            yield renderScriptBlock(request, "people.mako", "listPeople",
                                    landing, "#users-wrapper", "set", **args)
            yield renderScriptBlock(request, "people.mako", "paging",
                                landing, "#people-paging", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        viewType = utils.getRequestArg(request, "type") or "friends"
        start = utils.getRequestArg(request, "start") or ''
        d = None

        if segmentCount == 0:
            d = self._render(request, viewType, start)

        return self._epilogue(request, d)
