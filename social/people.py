import re
import sys
import struct
import random

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import db, utils, base, _, whitelist, blacklist
from social             import config, errors
from social.relations   import Relation
from social.template    import render, renderScriptBlock, getBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE, SUGGESTION_PER_PAGE
from social.logging     import dump_args, profile

INCOMING_REQUEST = '1'
OUTGOING_REQUEST = '0'

@defer.inlineCallbacks
def _update_suggestions(request):
    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username
    orgId = authinfo.organization
    relation = Relation(myId, [])
    weights = { 'friend': { 'friend': 100, 'follower': 30, 'subscription': 80, 'group': 50},
               'group': { 'friend': 50, 'follower': 15, 'subscription': 40, 'group': 60},
               'follower': { 'friend': 30, 'follower': 9, 'subscription': 24, 'group': 15},
               'subscription': { 'friend': 40, 'follower': 24, 'subscription': 64, 'group': 40}}
    defaultWeight = 1
    people = {}
    @defer.inlineCallbacks
    def _compute_weights(userIds, myGroups, type):
        friends = yield db.multiget_slice(userIds, "connections", count=50)
        followers = yield db.multiget_slice(userIds, "followers", count=50)
        subscriptions = yield db.multiget_slice(userIds, "subscriptions", count=50)
        groups = yield db.multiget_slice(userIds, "entityGroupsMap")
        friends = utils.multiSuperColumnsToDict(friends)
        followers = utils.multiColumnsToDict(followers)
        subscriptions = utils.multiColumnsToDict(subscriptions)
        for userId in friends:
            for friend in friends[userId]:
                people[friend] = people.setdefault(friend, defaultWeight)+ weights[type]['friend']
        for userId in followers:
            for follower in followers[userId]:
                people[follower] = people.setdefault(follower, defaultWeight) + weights[type]['follower']
        for userId in subscriptions:
            for subscription in subscriptions[userId]:
                people[subscription] = people.setdefault(subscription, defaultWeight) + weights[type]['subscription']
        for userId in groups:
            for groupId in groups[userId]:
                if groupId in myGroups:
                    people[userId] = people.setdefault(userId, defaultWeight) + weights[type]['group']



    yield defer.DeferredList([relation.initFriendsList(),
                               relation.initSubscriptionsList(),
                               relation.initPendingList(),
                               relation.initFollowersList(),
                               relation.initGroupsList()])
    if relation.friends:
        yield _compute_weights(relation.friends.keys(), relation.groups, 'friend')
    if relation.followers:
        yield _compute_weights(relation.followers, relation.groups, 'follower')
    if relation.subscriptions:
        yield _compute_weights(relation.subscriptions, relation.subscriptions, 'subscription')
    if relation.groups:
        groupMembers = yield db.multiget_slice(relation.groups, "groupMembers", count=20)
        groupMembers = utils.multiColumnsToDict(groupMembers)
        for groupId in groupMembers:
           yield  _compute_weights(groupMembers[groupId], relation.groups, 'group')


    cols = yield db.get_slice(orgId, "orgUsers", count=50)
    for col in cols:
        userId = col.column.name
        if userId not in people:
            people[userId] = people.setdefault(userId, 0) + defaultWeight

    suggestions = {}
    for userId in people:
        if userId in relation.friends or userId in relation.subscriptions or userId == myId:
            continue
        suggestions.setdefault(people[userId], []).append(userId)

    yield db.remove(myId, "suggestions")
    weights_userIds_map ={}
    format = '>l'
    for weight in suggestions:
        key = struct.pack(format, weight)
        weights_userIds_map[key] = ' '.join(suggestions[weight])
    yield db.batch_insert(myId, "suggestions", weights_userIds_map)


@defer.inlineCallbacks
def get_suggestions(request, count, mini=False):
    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username

    userIds = []
    update_suggestions = False
    relation = Relation(myId, [])
    yield defer.DeferredList([relation.initFriendsList(),
                               relation.initSubscriptionsList(),
                               relation.initPendingList(),
                               relation.initFollowersList()])

    @defer.inlineCallbacks
    def _get_suggestions(myId):
        cols = yield db.get_slice(myId, "suggestions", reverse=True)
        for col in cols:
            userIds.extend(col.column.value.split())

    def isValidSuggestion(suggestion):
        return not (suggestion in relation.friends or \
                    suggestion in relation.subscriptions or \
                    suggestion in relation.pending or
                    suggestion in relation.followers)

    yield _get_suggestions(myId)
    if not userIds:
        yield _update_suggestions(request)
        yield _get_suggestions(myId)

    if mini:
        no_of_samples = count*2
        population = count*5
        if len(userIds) < no_of_samples:
            suggestions = userIds[:]
        else:
            suggestions = random.sample(userIds[:population], no_of_samples)
    else:
        suggestions = userIds[:]
    if suggestions:
        foo = [(x, isValidSuggestion(x)) for x in suggestions]
        update_suggestions = any(zip(*foo)[1])
        suggestions = [suggestion for  suggestion, valid in foo if valid ]

    if mini and len(suggestions) < count:
        for userId in userIds:
            if userId not in suggestions:
                if isValidSuggestion(userId):
                    suggestions.append(userId)
                else:
                    update_suggestions = True
    if update_suggestions:
        _update_suggestions(request)

    entities = {}
    if suggestions:
        suggestions = suggestions[:count]
        entities = yield db.multiget_slice(suggestions, "entities", ['basic'])
        entities = utils.multiSuperColumnsToDict(entities)
    defer.returnValue((suggestions, entities))

@defer.inlineCallbacks
def _sendInvitations(myOrgUsers, otherOrgUsers, me, myId, myOrg):
    rootUrl = config.get('General', 'URL')
    brandName = config.get('Branding', 'Name')
    senderName = me["basic"]["name"]
    senderOrgName = myOrg["basic"]["name"]
    senderAvatarUrl = rootUrl + utils.userAvatar(myId, me, "medium")
    sentUsers = []
    blockedUsers = []
    existingUsers = []

    myOrgSubject = "%s invited you to %s" % (senderName, brandName)
    myOrgBody = "Hi,\n\n"\
                "%(senderName)s has invited you to %(senderOrgName)s network on %(brandName)s.\n"\
                "To activate your account please visit: %(activationUrl)s.\n\n"
    otherOrgSubject = "%s invited you to %s" % (senderName, brandName)
    otherOrgBody = "Hi,\n\n"\
                   "%(senderName)s has invited you to try %(brandName)s.\n"\
                   "To activate your account please visit: %(activationUrl)s.\n\n"

    signature =  "Flocked.in Team.\n\n\n\n"\
                 "--\n"\
                 "To block invitations from %(senderName)s visit %(blockSenderUrl)s\n"\
                 "To block all invitations from %(brandName)s visit %(blockAllUrl)s"

    blockSenderTmpl = "%(rootUrl)s/signup/blockSender?email=%(emailId)s&token=%(token)s"
    blockAllTmpl = "%(rootUrl)s/signup/blockAll?email=%(emailId)s&token=%(token)s"
    activationTmpl = "%(rootUrl)s/signup?email=%(emailId)s&token=%(token)s"

    # Combine all users.
    myOrgUsers.extend(otherOrgUsers)

    # Ensure that the users do not already exist and that the users are
    # not in the doNotSpam list (for this sender or globally)
    d1 = db.multiget(myOrgUsers, "userAuth", "user")
    d2 = db.multiget_slice(myOrgUsers, "doNotSpam", [myId, '*'])
    existing = yield d1
    existing = utils.multiColumnsToDict(existing)
    doNotSpam = yield d2
    doNotSpam = utils.multiColumnsToDict(doNotSpam)

    deferreds = []
    for emailId in myOrgUsers:
        if emailId in existing and existing[emailId]:
            existingUsers.append(emailId)
            continue

        token = utils.getRandomKey('invite')

        # Add invitation to the database
        localpart, domainpart = emailId.split('@')
        deferreds.append(db.insert(domainpart, "invitations", myId, token, emailId))
        deferreds.append(db.insert(myId, "invitationsSent", '', emailId))

        # Mail the invitation if everything is ok.
        if emailId in doNotSpam and doNotSpam[emailId]:
            blockedUsers.append(emailId)
            continue

        activationUrl = activationTmpl % locals()
        blockAllUrl = blockAllTmpl % locals()
        blockSenderUrl = blockSenderTmpl % locals()
        sameOrg = False if emailId in otherOrgUsers else True
        if not sameOrg:
            subject = otherOrgSubject
            textBody = (otherOrgBody + signature) % locals()
        else:
            subject = myOrgSubject
            textBody = (myOrgBody + signature) % locals()

        # XXX: getBlock blocks the application for disk reads when reading template
        htmlBody = getBlock("emails.mako", "invite", **locals())
        deferreds.append(utils.sendmail(emailId, subject, textBody, htmlBody))
        sentUsers.append(emailId)

    yield defer.DeferredList(deferreds)
    defer.returnValue((sentUsers, blockedUsers, existingUsers))


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

    stats = None
    if myOrgUsers or otherOrgUsers:
        stats = yield _sendInvitations(myOrgUsers, otherOrgUsers,
                                       entities[myId], myId, entities[myOrgId])
    defer.returnValue(stats)


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

        sentInvitationsCount = yield db.get_count(myId, "invitationsSent")

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

        # display the invitations tab only when there are invitations sent or
        # when user explicitly checks for viewType "invitations"
        showInvitationsTab = sentInvitationsCount > 0 or viewType == 'invitations'
        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart
        args["viewType"] = viewType
        args['showInvitationsTab'] = showInvitationsTab

        if script:
            yield renderScriptBlock(request, "people.mako", "viewOptions",
                                    landing, "#people-view", "set", args=[viewType],
                                    showInvitationsTab=showInvitationsTab)
            yield renderScriptBlock(request, "people.mako", "listPeople",
                                    landing, "#users-wrapper", "set", **args)
            yield renderScriptBlock(request, "people.mako", "paging",
                                landing, "#people-paging", "set", **args)

        if not script:
            yield render(request, "people.mako", **args)

    @defer.inlineCallbacks
    def _invite(self, request):
        src = utils.getRequestArg(request, 'from') or None
        rawEmailIds = request.args.get('email')
        stats = yield invite(request, rawEmailIds)

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

    @defer.inlineCallbacks
    def _renderSuggestions(self, request):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        suggestions, entities = yield get_suggestions(request, PEOPLE_PER_PAGE, True)
        #render suggestions

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
        elif segmentCount == 1 and request.postpath[0] == "suggestions":
            d = self._renderSuggestions(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 1 and request.postpath[0] == "invite":
            d = self._invite(request)

        return self._epilogue(request, d)
