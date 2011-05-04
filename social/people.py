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
    def _renderPeople(self, request, ):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        orgKey = args["orgKey"]
        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        args["entities"] = {}
        args["heading"] = _("Organization People")

        if not orgKey:
            errors.MissingParams()

        if script and landing:
            yield render(request, "people.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        users, relation, userIds, \
            blockedUsers, nextPageStart = yield getPeople(myId, args["orgKey"],
                                                    args["orgKey"],
                                                    start=start)

        # First result tuple contains the list of user objects.
        args["entities"] = users
        args["relations"] = relation
        args["people"] = userIds
        args["nextPageStart"] = nextPageStart

        if script:
            if fromFetchMore:
                yield renderScriptBlock(request, "people.mako", "employees", landing,
                                        "#next-load-wrapper", "replace", True,
                                        handlers={}, **args)
            else:
                yield renderScriptBlock(request, "people.mako", "employees",
                                        landing, "#users-wrapper", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)


    @defer.inlineCallbacks
    def _getFriends(self, userId, start, count=PEOPLE_PER_PAGE):
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
    @defer.inlineCallbacks
    @dump_args
    def _renderFriends(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax

        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        args["entities"] = {}
        args["heading"] = _("My Friends")

        if script and landing:
            yield render(request,"people.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)


        users, relation, userIds, \
            blockedUsers, nextPageStart = yield getPeople(myId, myId,
                                                            args["orgKey"],
                                                            start=start,
                                                            fn=self._getFriends)
        args["entities"] = users
        args["relations"] = relation
        args["people"] = userIds
        args["nextPageStart"] = nextPageStart

        if script:
            if fromFetchMore:
                yield renderScriptBlock(request, "people.mako", "friends", landing,
                                        "#next-load-wrapper", "replace", True,
                                        handlers={}, **args)
            else:
                yield renderScriptBlock(request, "people.mako", "friends",
                                        landing, "#users-wrapper", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderPeople(request)
        elif segmentCount == 1 and request.postpath[0]=="friends":
            d = self._renderFriends(request)

        return self._epilogue(request, d)
