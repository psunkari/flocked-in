import re
import sys
import struct
import random
import time

from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, _, whitelist, blacklist
from social             import config, errors, template as t
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE, SUGGESTION_PER_PAGE
from social.logging     import dump_args, profile, log


INCOMING_REQUEST = 'FI'
OUTGOING_REQUEST = 'FO'


def isValidSuggestion(myId, userId, relation):
    return not (userId in relation.subscriptions or \
                userId in relation.followers or
                userId == myId)

@defer.inlineCallbacks
def _update_suggestions(request, relation=None):
    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username
    orgId = authinfo.organization
    weights = {'group': { 'follower': 15, 'subscription': 40, 'group': 30},
               'follower': { 'follower': 9, 'subscription': 24, 'group': 15},
               'subscription': { 'follower': 24, 'subscription': 64, 'group': 40}}
    defaultWeight = 1
    people = {}
    @defer.inlineCallbacks
    def _compute_weights(userIds, myGroups, type):
        followers = yield db.multiget_slice(userIds, "followers", count=50)
        subscriptions = yield db.multiget_slice(userIds, "subscriptions", count=50)
        groups = yield db.multiget_slice(userIds, "entityGroupsMap")
        followers = utils.multiColumnsToDict(followers)
        subscriptions = utils.multiColumnsToDict(subscriptions)
        groups = utils.multiColumnsToDict(groups)
        for userId in followers:
            for follower in followers[userId]:
                people[follower] = people.setdefault(follower, defaultWeight) + weights[type]['follower']
        for userId in subscriptions:
            for subscription in subscriptions[userId]:
                people[subscription] = people.setdefault(subscription, defaultWeight) + weights[type]['subscription']
        for userId in groups:
            groupIds = [x.split(':', 1)[1] for x in groups[userId]]
            for groupId in groupIds:
                if groupId in myGroups:
                    people[userId] = people.setdefault(userId, defaultWeight) + weights[type]['group']

    if not relation:
        relation = Relation(myId, [])
        yield defer.DeferredList([relation.initSubscriptionsList(),
                                  relation.initFollowersList(),
                                  relation.initGroupsList()])
    if relation.followers:
        yield _compute_weights(relation.followers, relation.groups, 'follower')
    if relation.subscriptions:
        yield _compute_weights(relation.subscriptions, relation.groups, 'subscription')
    if relation.groups:
        groupMembers = yield db.multiget_slice(relation.groups, "groupMembers", count=20)
        groupMembers = utils.multiColumnsToDict(groupMembers)
        for groupId in groupMembers:
            yield  _compute_weights(groupMembers[groupId], relation.groups, 'group')

    cols = yield db.get_slice(orgId, "orgUsers", count=100)
    for col in cols:
        userId = col.column.name
        if userId not in people:
            people[userId] = people.setdefault(userId, 0) + defaultWeight

    suggestions = {}
    for userId in people:
        if isValidSuggestion(myId, userId, relation):
            suggestions.setdefault(people[userId], []).append(userId)

    yield db.remove(myId, "suggestions")
    weights_userIds_map ={}
    format = '>l'
    for weight in suggestions:
        key = struct.pack(format, weight)
        weights_userIds_map[key] = ' '.join(suggestions[weight])
    if weights_userIds_map:
        yield db.batch_insert(myId, "suggestions", weights_userIds_map)


@defer.inlineCallbacks
def get_suggestions(request, count, mini=False):
    authinfo = request.getSession(IAuthInfo)
    myId = authinfo.username

    SUGGESTIONS_UPDATE_FREQUENCY = 3 * 86400 # 5days
    MAX_INVALID_SUGGESTIONS = 3
    now = time.time()

    suggestions = []
    relation = Relation(myId, [])
    yield defer.DeferredList([relation.initSubscriptionsList(),
                              relation.initFollowersList()])

    @defer.inlineCallbacks
    def _get_suggestions(myId, relation):
        validSuggestions = []
        invalidCount = 0
        FORCE_UPDATE = False
        cols = yield db.get_slice(myId, "suggestions", reverse=True)
        for col in cols:
            if now - col.column.timestamp/1e6 > SUGGESTIONS_UPDATE_FREQUENCY:
                FORCE_UPDATE = True
            for userId in col.column.value.split():
                if isValidSuggestion(myId, userId, relation):
                    validSuggestions.append(userId)
                else:
                    invalidCount +=1
        defer.returnValue((validSuggestions, invalidCount, FORCE_UPDATE))

    validSuggestions, invalidCount, FORCE_UPDATE = yield _get_suggestions(myId, relation)
    if not validSuggestions:
        yield _update_suggestions(request, relation)
        validSuggestions, invalidCount, FORCE_UPDATE = yield _get_suggestions(myId, relation)

    no_of_samples = count*2
    population = count*5
    if mini and len(validSuggestions)>= no_of_samples:
        suggestions = random.sample(validSuggestions[:population], no_of_samples)
    else:
        suggestions = validSuggestions[:]

    if FORCE_UPDATE or invalidCount > MAX_INVALID_SUGGESTIONS:
        _update_suggestions(request, relation)

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
    senderAvatarUrl = utils.userAvatar(myId, me, "medium")
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

        token = utils.getRandomKey()

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
        htmlBody = t.getBlock("emails.mako", "invite", **locals())
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
                log.info("%s is blacklisted" %(domainpart))
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
def _getPendingConnections(userId, start='', count=PEOPLE_PER_PAGE, entityType='user'):
    toFetchCount = count + 1
    toFetchStart = start if start else INCOMING_REQUEST
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
        #TOFIX: len(col.column.name.split(':')) == 2 is not necessary
        ids = [col.column.name.split(':')[1] for col in cols if len(col.column.name.split(':')) ==2 and col.column.name.split(':')[0] == INCOMING_REQUEST]
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
        nextPageStart = utils.encodeKey(":".join([INCOMING_REQUEST, entityIds[-1]]))
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
            ids = [col.column.name.split(':', 1)[1] for col in cols if len(col.column.name.split(':')) == 2 and col.column.name.split(':')[0] == INCOMING_REQUEST]
            if ids:
                tmp_entities = yield db.multiget_slice(ids, "entities", ["basic"])
                tmp_entities = utils.multiSuperColumnsToDict(tmp_entities)
                for entityId in ids:
                    if tmp_entities[entityId]['basic']['type'] == entityType and \
                       entityId not in tmp_ids:
                        tmp_count +=1
                        tmp_ids.append(entityId)
                    if tmp_count == toFetchCount:
                        prevPageStart = utils.encodeKey(':'.join([INCOMING_REQUEST, entityId]))
                        break
            if len(cols) < toFetchCount:
                break
    yield relation_d

    defer.returnValue((entities, relation, entityIds,\
                       blockedUsers, nextPageStart, prevPageStart))


class PeopleResource(base.BaseResource):
    isLeaf = True
    _templates = ['people.mako', 'emails.mako']

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
            t.render(request, "people.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "people.mako", "layout",
                                landing, "#mainbar", "set", **args)

        d = None
        if viewType == "all":
            d = getPeople(myId, orgId, orgId, start=start, fetchBlocked=False)
        elif viewType == "invitations":
            d = _getInvitationsSent(myId, start=start)
        else:
            raise errors.InvalidRequest(_("Unknown view type"))

        sentInvitationsCount = yield db.get_count(myId, "invitationsSent")

        if viewType == 'all':
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
            t.renderScriptBlock(request, "people.mako", "viewOptions",
                                landing, "#people-view", "set", args=[viewType],
                                showInvitationsTab=showInvitationsTab)
            t.renderScriptBlock(request, "people.mako", "listPeople",
                                landing, "#users-wrapper", "set", **args)
            t.renderScriptBlock(request, "people.mako", "paging",
                                landing, "#people-paging", "set", **args)

        if not script:
            t.render(request, "people.mako", **args)

    @defer.inlineCallbacks
    def _invite(self, request):
        src = utils.getRequestArg(request, 'from') or None
        rawEmailIds = request.args.get('email')
        stats = yield invite(request, rawEmailIds)

        if not src:
            src = "sidebar" if len(rawEmailIds) == 1 else "people"
        if src == "sidebar" and self._ajax:
            request.write("$('#invite-others').val('');" )
        elif src == "sidebar":
            request.redirect('/feed/')
        elif src == "people" and self._ajax:
            pass
        elif src == "people":
            request.redirect('/people')
        if not stats and self._ajax:
            request.write("$$.alerts.error('%s');" \
                            %(_("Use company email addresses only.")))
        elif stats and self._ajax:
            if len(stats[0]) == 1:
                request.write("$$.alerts.info('%s');" %_("Invitation sent"))
                request.write("$$.dialog.close('invitepeople-dlg', true);")
            elif len(stats[0]) >1:
                request.write("$$.alerts.info('%s');" %_("Invitations sent"))
                request.write("$$.dialog.close('invitepeople-dlg', true);")
            else:
                #TODO: when user tries to send invitations to existing members,
                #      show these members as add-as-friend/follow list
                request.write("$$.alerts.info('%s');\
                               $$.dialog.close('invitepeople-dlg', true);" \
                               %_("Invitations sent"))


    def _renderInvitePeople(self, request):
        t.renderScriptBlock(request, "people.mako", "invitePeople",
                            False, "#invitepeople-dlg", "set")
        return True


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
        viewType = utils.getRequestArg(request, "type") or "all"
        start = utils.getRequestArg(request, "start") or ""
        start = utils.decodeKey(start)
        d = None

        if segmentCount == 0:
            d = self._render(request, viewType, start)
        elif segmentCount == 1 and self._ajax and request.postpath[0] == "invite":
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
