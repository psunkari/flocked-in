from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base, _
from social.relations   import Relation
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE


class PeopleResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _renderPeople(self, request, ):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        orgKey = args["orgKey"]
        start = utils.getRequestArg(request, "start") or ''
        args["entities"] = {}
        args["heading"] = _("Organization People")

        if not orgKey:
            errors.MissingParams()

        if script and landing:
            yield render(request, "people.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        employees = yield Db.get_slice(orgKey, "orgUsers",
                                       start=start, count=PEOPLE_PER_PAGE)
        employees = [employee.column.name for employee in employees]

        usersDeferred = Db.multiget_slice(employees, "entities", ["basic"])
        relation = Relation(myKey, employees)
        results = yield defer.DeferredList([usersDeferred,
                                            relation.initFriendsList(),
                                            relation.initPendingList(),
                                            relation.initSubscriptionsList()])

        # First result tuple contains the list of user objects.
        args["entities"] = utils.multiSuperColumnsToDict(results[0][1])
        args["relations"] = relation

        if script:
            yield renderScriptBlock(request, "people.mako", "content",
                                    landing, "#users-wrapper", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)


    @defer.inlineCallbacks
    def _renderFriends(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        start = utils.getRequestArg(request, "start") or ''
        args["entities"] = {}
        args["heading"] = _("My Friends")

        if script and landing:
            yield render(request,"people.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        friends = yield Db.get_slice(myKey, "connections",
                                     start=start, count=PEOPLE_PER_PAGE)
        friends = dict((x.super_column.name,\
                        [y.value for y in x.super_column.columns])\
                       for x in friends)

        relation = Relation(myKey, friends.keys())
        relation.friends = friends
        entities = yield Db.multiget_slice(friends.keys(), "entities", ["basic"])

        args["entities"] = utils.multiSuperColumnsToDict(entities)
        args["relations"] = relation

        if script:
            yield renderScriptBlock(request, "people.mako", "content",
                                    landing, "#users-wrapper", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderPeople(request)
        elif segmentCount == 1 and request.postpath[0]=="friends":
            d = self._renderFriends(request)

        return self._epilogue(request, d)
