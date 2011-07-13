import re

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import db, utils, base, _, whitelist, blacklist, config
from social.relations   import Relation
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE
from social.logging     import dump_args, profile

INCOMING_REQUEST = '1'
OUTGOING_REQUEST = '0'

@defer.inlineCallbacks
def _sendInvitations(myOrgUsers, otherOrgUsers, me, myId, myOrg):
    rootUrl = config.get('General', 'URL')
    brandName = config.get('Branding', 'Name')
    myName = me["basic"]["name"]
    myOrgName = myOrg["basic"]["name"]
    deferreds = []

    myOrgSubject = "%s invited you to %s" % (myName, brandName)
    myOrgBody = "Hi,\n\n"\
                "%(myName)s has invited you to %(myOrgName)s network on %(brandName)s.\n"\
                "To activate your account please visit: %(activationUrl)s.\n\n"\
                "Flocked.in Team."
    otherOrgSubject = "%s invited you to %s" % (myName, brandName)
    otherOrgBody = "Hi,\n\n"\
                   "%(myName)s has invited you to try %(brandName)s.\n"\
                   "To activate your account please visit: %(activationUrl)s.\n\n"\
                   "Flocked.in Team."

    myOrgUsers.extend(otherOrgUsers)
    for emailId in myOrgUsers:
        token = utils.getRandomKey('invite')
        activationUrl = "%(rootUrl)s/signup?email=%(emailId)s&token=%(token)s" % (locals())
        localpart, domainpart = emailId.split('@')

        deferreds.append(db.insert(domainpart, "invitations", myId, token, emailId))
        deferreds.append(db.insert(myId, "invitationsSent", '', emailId))
        if emailId in otherOrgUsers:
            deferreds.append(utils.sendmail(emailId, otherOrgSubject, otherOrgBody%locals()))
        else:
            deferreds.append(utils.sendmail(emailId, myOrgSubject, myOrgBody%locals()))

    yield defer.DeferredList(deferreds)


@defer.inlineCallbacks
def invite(request, rawEmailIds):
    authinfo = request.getSession(IAuthInfo)
    emailIds = []

    expr = re.compile(', *')
    for commaSeparated in rawEmailIds:
        emailIds.extend(expr.split(commaSeparated))

    myId = authinfo.username
    myOrgId = authinfo.organization
    entities = yield db.multiget_slice([myId, myOrgId], "entities",
                                       ["basic", "domains"])
    entities = utils.multiSuperColumnsToDict(entities)
    myOrgDomains = set(entities[myOrgId].get('domains').keys())
    myOrgIsWhite = len(myOrgDomains.intersection(whitelist))

    myOrgUsers = []
    otherOrgUsers = []
    for emailId in emailIds:
        try:
            localpart, domainpart = emailId.split('@')
            if domainpart in blacklist:
                pass
            elif domainpart in myOrgDomains:
                myOrgUsers.append(emailId)
            elif myOrgIsWhite:
                otherOrgUsers.append(emailId)
        except:
            pass

    if myOrgUsers or otherOrgUsers:
        _sendInvitations(myOrgUsers, otherOrgUsers,
                         entities[myId], myId, entities[myOrgId])


@defer.inlineCallbacks
def getPeople(myId, entityId, orgId, start='',
              count=PEOPLE_PER_PAGE, fn=None, fetchBlocked=True):
    blockedUsers = []
    toFetchCount = count + 1
    nextPageStart = None
    prevPageStart = None
    userIds = []

    if fetchBlocked:
        cols = yield db.get_slice(orgId, "blockedUsers")
        blockedUsers = utils.columnsToDict(cols).keys()

    if not fn:
        d1 = db.get_slice(entityId, "displayNameIndex",
                          start=start, count=toFetchCount)
        d2 = db.get_slice(entityId, "displayNameIndex",
                          start=start, count=toFetchCount,
                          reverse=True) if start else None

        # Get the list of users (sorted by displayName)
        cols = yield d1
        userIds = [col.column.name.split(":")[1] for col in cols]
        if len(userIds) > count:
            nextPageStart = utils.encodeKey(cols[-1].column.name)
            userIds = userIds[0:count]

        toFetchUsers = userIds

        # Start of previous page
        if start and d2:
            prevCols = yield d2
            if len(prevCols) > 1:
                prevPageStart = utils.encodeKey(prevCols[-1].column.name)
    else:
        userIds, nextPageStart, prevPageStart\
                                = yield fn(entityId, start, toFetchCount)
        toFetchUsers = userIds

    usersDeferred = db.multiget_slice(toFetchUsers, "entities", ["basic"])
    relation = Relation(myId, userIds)
    results = yield defer.DeferredList([usersDeferred,
                                        relation.initFriendsList(),
                                        relation.initPendingList(),
                                        relation.initSubscriptionsList()])
    users = utils.multiSuperColumnsToDict(results[0][1])

    defer.returnValue((users, relation, userIds,\
                       blockedUsers, nextPageStart, prevPageStart))


@defer.inlineCallbacks
def _getInvitationsSent(userId, start='', count=PEOPLE_PER_PAGE):
    toFetchCount = count + 1
    prevPageStart = None
    nextPageStart = None
    d1 = db.get_slice(userId, "invitationsSent",
                      start=start, count=toFetchCount)
    d2 = db.get_slice(userId, "invitationsSent", start=start,
                      count=toFetchCount, reverse=True) if start else None
    cols = yield d1
    emailIds = [col.column.name for col in cols]
    if len(cols) == toFetchCount:
        nextPageStart = utils.encodeKey(emailIds[-1])
        emailIds = emailIds[0:count]

    if start and d2:
        prevCols = yield d2
        if len(prevCols) > 1:
            prevPageStart = utils.encodeKey(prevCols[-1].column.name)

    defer.returnValue((emailIds, prevPageStart, nextPageStart))

@defer.inlineCallbacks
def _get_pending_conncetions(userId, start='', count=PEOPLE_PER_PAGE, entityType='user'):
    toFetchCount = count + 1
    toFetchStart = start
    prevPageStart = None
    nextPageStart = None
    blockedUsers = []
    entityIds = []
    entities = {}
    tmp_count = 0

    while len(entities) < toFetchCount:
        cols = yield db.get_slice(userId, "pendingConnections",
                                  start=toFetchStart,
                                  count=toFetchCount)
        if cols:
            toFetchStart = cols[-1].column.name

        ids = [col.column.name for col in cols if col.column.value == INCOMING_REQUEST]
        if ids:
            tmp_entities = yield db.multiget_slice(ids, "entities", ["basic"])
            tmp_entities = utils.multiSuperColumnsToDict(tmp_entities)
            for entityId in ids:
                if tmp_entities[entityId]['basic']['type'] == entityType and \
                   entityId not in entityIds:
                    entities[entityId] = tmp_entities[entityId]
                    entityIds.append(entityId)
                    tmp_count +=1
                if tmp_count == toFetchCount:
                    break

        if len(cols) < toFetchCount:
            break

    if len(entities) == toFetchCount:
        nextPageStart = entityIds[-1]
        entityIds = entityIds[0:count]
    relation = Relation(userId, entityIds)
    relation_d =  defer.DeferredList([relation.initPendingList(),
                                      relation.initSubscriptionsList()])

    if start:
        tmp_count = 0
        toFetchStart = start
        tmp_ids = []
        while tmp_count < toFetchCount:
            cols = yield db.get_slice(userId, "pendingConnections",
                                     start=toFetchStart, count=toFetchCount,
                                     reverse=True)
            if cols:
                toFetchStart = cols[-1].column.name
            ids = [col.column.name for col in cols if col.column.value == INCOMING_REQUEST]
            if ids:
                tmp_entities = yield db.multiget_slice(ids, "entities", ["basic"])
                tmp_entities = utils.multiSuperColumnsToDict(tmp_entities)
                for entityId in ids:
                    if tmp_entities[entityId]['basic']['type'] == entityType and \
                       entityId not in tmp_ids:
                        tmp_count +=1
                        tmp_ids.append(entityId)
                    if tmp_count == toFetchCount:
                        prevPageStart = entityId
                        break
            if len(cols) < toFetchCount:
                break
    yield relation_d

    defer.returnValue((entities, relation, entityIds,\
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
            d = getPeople(myId, orgId, orgId, start=start, fetchBlocked=False)
        elif viewType == "friends":
            d = getPeople(myId, myId, orgId, start=start, fetchBlocked=False)
        elif viewType == 'pendingRequests':
            d = _get_pending_conncetions(myId, start=start)
        elif viewType == "invitations":
            d = _getInvitationsSent(myId, start=start)
        else:
            raise errors.InvalidRequest(_("Unknown view type"))

        if viewType in ['all', 'friends', 'pendingRequests']:
            users, relations, userIds,\
                blockedUsers, nextPageStart, prevPageStart = yield d

            # First result tuple contains the list of user objects.
            args["entities"] = users
            args["relations"] = relations
            args["people"] = userIds
        elif viewType == 'invitations':
            emailIds, prevPageStart, nextPageStart = yield d
            args['emailIds'] = emailIds

        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["viewType"] = viewType

        if script:
            yield renderScriptBlock(request, "people.mako", "viewOptions",
                                landing, "#people-view", "set", args=[viewType])
            if viewType in ('all', 'friends', 'pendingRequests'):
                yield renderScriptBlock(request, "people.mako", "listPeople",
                                        landing, "#users-wrapper", "set", **args)
            elif viewType == 'invitations':
                yield renderScriptBlock(request, "people.mako", "listInvitations",
                                        landing, "#users-wrapper", "set", **args)
            yield renderScriptBlock(request, "people.mako", "paging",
                                landing, "#people-paging", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)

    @defer.inlineCallbacks
    def _invite(self, request):
        src = utils.getRequestArg(request, 'from') or None
        rawEmailIds = request.args.get('email')
        d = invite(request, rawEmailIds)

        if not src:
            src = "sidebar" if len(rawEmailIds) == 1 else "people"

        if src == "sidebar" and self._ajax:
            yield renderScriptBlock(request, "feed.mako", "invitePeopleBlock",
                                    False, "#invite-people-block", "set")
        elif src == "sidebar":
            request.redirect('/feed')
        elif src == "people" and self._ajax:
            request.write("$('#invite-people-wrapper').empty()")
        elif src == "people":
            request.redirect('/people')

    @defer.inlineCallbacks
    def _renderInvitePeople(self, request):
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

        if script:
            onload = """
                    $$.ui.placeholders('#invite-people input:text');
                    (function(obj){$$.publisher.load(obj);
                        $('#invite-people').delegate('.input-wrap:last-child','focus',function(event){
                            $(event.target.parentNode).clone().appendTo('#invite-people').find('input:text').blur();
                        });
                    })(this);
                    """
            yield renderScriptBlock(request, "people.mako", "invitePeople",
                                    landing, "#invite-people-wrapper", "set", True,
                                    handlers={"onload":onload}, **args)

        else:
            yield render(request, "people.mako", **args)

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        viewType = utils.getRequestArg(request, "type") or "friends"
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)
        d = None

        if segmentCount == 0:
            d = self._render(request, viewType, start)
        elif segmentCount == 1 and request.postpath[0] == "invite":
            d = self._renderInvitePeople(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1 and request.postpath[0] == "invite":
            d = self._invite(request)

        return self._epilogue(request, d)
