from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, base
from social.template    import render, renderScriptBlock
from social.auth        import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE


class PeopleResource(base.BaseResource):
    isLeaf = True
    @defer.inlineCallbacks
    def _renderPeople(self, request, ):
        (appchange, script, args) = self._getBasicArgs(request)
        landing = not self._ajax

        orgKey = args["orgKey"]
        myKey = args["myKey"]
        start = utils.getRequestArg(request, "start") or ''

        cols = yield Db.get_slice(myKey, "users")
        me = utils.supercolumnsToDict(cols)
        args["me"] = me
        args["users"] = {}

        if not orgKey:
            errors.MissingParams()

        if script and landing:
            yield render(request,"people.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)


        employees = yield Db.get_slice(orgKey, "orgUsers",
                                       start=start, count=PEOPLE_PER_PAGE)
        employees = [employee.column.name for employee in employees]

        users = yield Db.multiget_slice(employees, "users", ["basic"])
        myFriends = yield Db.get_slice(myKey, "connections")
        mySubscriptions = yield Db.get_slice(myKey, "subscriptions")

        args["heading"] = "People"
        args["users"] = utils.multiSuperColumnsToDict(users)
        args["myFriends"] = utils.supercolumnsToDict(myFriends)
        args["mySubscriptions"] = utils.columnsToDict(mySubscriptions)

        if script:
            yield renderScriptBlock(request, "people.mako", "content",
                                    landing, "#center", "set", **args)


    @defer.inlineCallbacks
    def _renderFriends(self, request):
        (appchange, script, args) = self._getBasicArgs(request)
        landing = not self._ajax

        myKey = args["myKey"]
        start = utils.getRequestArg(request, "start") or ''

        cols = yield Db.get_slice(myKey, "users")
        me = utils.supercolumnsToDict(cols)

        args["me"] = me
        args["users"] = {}

        if script and landing:
            yield render(request,"people.mako", **args)
        if script and appchange:
            yield renderScriptBlock(request, "people.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        friends = yield Db.get_slice(myKey, "connections",
                                     start=start, count=PEOPLE_PER_PAGE)
        friends = utils.supercolumnsToDict(friends)
        #friends = [friend.super_column.name for friend in friends]
        users = yield Db.multiget_slice(friends.keys(), "users", ["basic"])

        args["heading"] = "Friends"
        args["users"] = utils.multiSuperColumnsToDict(users)
        args["myFriends"] = friends

        if script:
            yield renderScriptBlock(request, "people.mako", "content",
                                    landing, "#center", "set", **args)

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._renderPeople(request)
        if segmentCount == 1 and request.postpath[0]=="friends":
            d = self._renderFriends(request)
        if d:
            def callback(res):
                request.finish()
            def errback(err):
                log.msg(err)
                request.finish()
            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET