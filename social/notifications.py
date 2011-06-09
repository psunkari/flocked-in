import uuid
import time
import json

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, Db, utils, feed, plugins, constants, _
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import dump_args, profile


@profile
@defer.inlineCallbacks
@dump_args
def pushNotifications(itemId, convId, responseType, convType, convOwner,
                      commentOwner, timeUUID, followers=None, sc = "notifications"):
    # value = responseType:commentOwner:itemKey:convType:convOwner:
    value = ":".join([responseType, commentOwner, itemId, convType, convOwner])
    if not followers:
        followers = yield Db.get_slice(convId, "items", super_column="followers")
    deferreds = []

    for follower in followers:
        userKey = follower.column.name
        if commentOwner != userKey:
            d1 =  Db.insert(userKey, "notifications", convId, timeUUID)
            d2 =  Db.insert(userKey, "latestNotifications", convId, timeUUID, sc)
            d3 =  Db.batch_insert(userKey, "notificationItems", {convId:{timeUUID:value}})
            deferreds.extend([d1, d2, d3])
    yield defer.DeferredList(deferreds)


@profile
@defer.inlineCallbacks
@dump_args
def deleteNotifications(convId, timeUUID, followers=None, sf="notifications"):
    deferreds = []
    if not followers:
        followers = yield Db.get_slice(convId, "items", super_column="followers")
    for follower in followers:
        userKey = follower.column.name
        d1 = Db.remove(userKey, "notifications", timeUUID)
        d2 = Db.remove(userKey, "latestNotifications", timeUUID, sf)
        d3 = Db.remove(userKey, "notificationItems", timeUUID, convId)
        deferreds.extend([d1, d2, d3])
    yield defer.DeferredList(deferreds)


class NotificationsResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _getNotifications(self, request, count=15):
        def _getReasonStr(template, convId, itemType, itemOwnerId, usersList):

            vals = []
            noOfUsers = len(set(usersList))
            for userId in usersList:
                userName = utils.userName(userId, users[userId])
                if userName not in vals:
                    vals.append(userName)
                if len(vals) == noOfUsers or len(vals) == 2:
                    break
            if noOfUsers > 3:
                vals.append(noOfUsers-2)
            vals.append(utils.userName(itemOwnerId, users[itemOwnerId]))
            vals.append(utils.itemLink(convId, itemType))
            return _(template) %(tuple(vals))

        args = {}
        convs = []
        comments = {}
        answers = {}
        reasonStr = {}
        convLikes = {}
        commentLikes = {}
        answerLikes = {}
        pluginNotifications = {}
        toFetchUsers = set()
        toFetchGroups = set()
        pendingRequests = {}
        fetchCount = count + 1
        nextPageStart = None

        myId = request.getSession(IAuthInfo).username
        fetchStart = utils.getRequestArg(request, "start") or ''
        if fetchStart:
            fetchStart = utils.decodeKey(fetchStart)

        while len(convs) < count:
            cols = yield Db.get_slice(myId, "notifications", count=fetchCount,
                                      start=fetchStart, reverse=True)
            for col in cols:
                value = col.column.value
                if value not in convs:
                    convs.append(value)

            fetchStart = cols[-1].column.name
            if len(convs)> count:
                nextPageStart = utils.encodeKey(fetchStart)

            if len(cols) < fetchCount:
                break

        if len(convs) > count:
            convs = convs[0:count]

        args["conversations"] = convs
        if not convs:
            defer.returnValue(args)

        rawNotifications = yield Db.get_slice(myId, "notificationItems",
                                              convs, reverse=True)
        #reverse isn't working: the column order is not changing when revers=False
        #So, adding userIds in reverse order. (insert at 0th position instead of append)
        rawNotifications = utils.supercolumnsToDict(rawNotifications, ordered=True)
        for convId in rawNotifications:
            for timeUUID, value in rawNotifications[convId].items():
                responseType, commentOwner, itemId,\
                                convType, convOwner = value.split(":")
                key = (convId, convType, convOwner)
                toFetchUsers.add(commentOwner)
                toFetchUsers.add(convOwner)
                if responseType == "C":
                    comments.setdefault(key, [])
                    if commentOwner not in comments[key]:
                        comments[key].insert(0,commentOwner)
                elif responseType == "L" and itemId == convId:
                    convLikes.setdefault(key, [])
                    if commentOwner not in convLikes[key]:
                        convLikes[key].insert(0,commentOwner)
                elif responseType == "L" and itemId != convId:
                    if convType == "question":
                        answerLikes.setdefault(key, [])
                        if commentOwner not in answerLikes[key]:
                            answerLikes[key].insert(0,commentOwner)
                    else:
                        commentLikes.setdefault(key, [])
                        if commentOwner not in commentLikes[key]:
                            commentLikes[key].insert(0,commentOwner)
                elif responseType == "I" and convType in plugins:
                    pluginNotifications.setdefault(convType, {})
                    pluginNotifications[convType].setdefault(convId, [])
                    if commentOwner not in pluginNotifications[convType][convId]:
                        pluginNotifications[convType][convId].insert(0,commentOwner)
                elif responseType == "G":
                    groupId = convId
                    toFetchGroups.add(groupId)
                    pendingRequests.setdefault(groupId, [])
                    if commentOwner not in pendingRequests[groupId]:
                        pendingRequests[groupId].insert(0,commentOwner)
                elif responseType == 'Q':
                    answers.setdefault(key, [])
                    if commentOwner not in answers[key]:
                        answers[key].insert(0,commentOwner)

        users = yield Db.multiget_slice(toFetchUsers, "entities", ["basic"])
        groups = yield Db.multiget_slice(toFetchGroups, "entities", ["basic"])

        users = utils.multiSuperColumnsToDict(users)
        groups = utils.multiSuperColumnsToDict(groups)

        commentTemplate = {1: "%s commented on %s's %s",
                           2: "%s and %s commented on %s's %s",
                           3: "%s, %s and 1 other commented on %s's %s",
                           4: "%s, %s and %s others commented on %s's %s"}
        likesTemplate = {1: "%s likes %s's %s",
                         2: "%s and %s likes %s's %s",
                         3: "%s, %s and 1 other likes %s's %s",
                         4: "%s, %s and %s others likes %s's %s"}
        commentLikesTemplate = {1: "%s likes a comment on %s's %s",
                                 2: "%s and %s likes a comment on  %s's %s",
                                 3: "%s, %s and 1 other likes a comment on  %s's %s",
                                 4: "%s, %s and %s others likes a comment on %s's %s"}
        groupRequestsTemplate = {1: "%s subscribed to %s group. %s to approve the request ",
                                 2: "%s and %s subscribed to %s group. %s to approve the request",
                                 3: "%s and %s and 1 other subscribed to %s group. %s to approve the request.",
                                 4: "%s and %s and %s others subscribed to %s group. %s to approve the request."}
        answersTemplate = {1: "%s answered %s's %s",
                           2: "%s and %s answered %s's %s",
                           3: "%s, %s and 1 other answered %s's %s",
                           4: "%s, %s and %s others answered %s's %s"}
        answerLikesTemplate = {1: "%s likes an answer on %s's %s",
                                 2: "%s and %s likes an answer on  %s's %s",
                                 3: "%s, %s and 1 other likes an answer on  %s's %s",
                                 4: "%s, %s and %s others likes an answer on %s's %s"}

        for convId in convs:
            reasonStr[convId] = []

        for key in comments:
            convId, convType, convOwner = key
            template = commentTemplate[len(comments[key][:4])]
            reason = _getReasonStr(template, convId, convType, convOwner, comments[key])
            reasonStr[convId].append(reason)

        for key in convLikes:
            convId, convType, convOwner = key
            template = likesTemplate[len(convLikes[key][:4])]
            reason = _getReasonStr(template, convId, convType, convOwner, convLikes[key])
            reasonStr[convId].append(reason)

        for key in commentLikes:
            convId, convType, convOwner = key
            template = commentLikesTemplate[len(commentLikes[key][:4])]
            reason = _getReasonStr(template, convId, convType, convOwner, commentLikes[key])
            reasonStr[convId].append(reason)

        for key in answers:
            convId, convType, convOwner = key
            template = answersTemplate[len(answers[key][:4])]
            reason = _getReasonStr(template, convId, convType, convOwner, answers[key])
            reasonStr[convId].append(reason)

        for key in answerLikes:
            convId, convType, convOwner = key
            template = answerLikesTemplate[len(answerLikes[key][:4])]
            reason = _getReasonStr(template, convId, convType, convOwner, answerLikes[key])
            reasonStr[convId].append(reason)

        for convType in pluginNotifications:
            for convId in pluginNotifications[convType]:
                reason = yield plugins[convType].getReason(convId,
                                                     pluginNotifications[convType][convId],
                                                     users)
                reasonStr[convId].append(reason)

        for groupId in pendingRequests:
            groupName = groups[groupId]["basic"]["name"]
            groupUrl = "<a href='/feed?id=%s'> %s</a>"%(groupId, groupName)
            url = "<a href='/groups/admin?id=%s'>click here</a> "%(groupId)
            reason = groupRequestsTemplate[len(pendingRequests[groupId])]
            vals = [utils.userName(userId, users[userId]) for userId in pendingRequests[groupId][:2]]
            if len(pendingRequests[groupId])>3:
                vals.append(len(pendingRequests[groupId])-2)
            vals.append(groupUrl)
            vals.append(url)
            reasonStr[groupId].append(reason%(tuple(vals)))

        args["reasonStr"] = reasonStr
        args["groups"] = groups
        args["users"] = users
        args["nextPageStart"] = nextPageStart

        defer.returnValue(args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderNotifications(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        args["menuId"] = "notifications"

        if script and landing:
            yield render(request, "notifications.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "notifications.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        data = yield self._getNotifications(request)
        if not start:
            yield Db.remove(myId, "latestNotifications", super_column="notifications")
        args.update(data)

        if script:
            if fromFetchMore:
                yield renderScriptBlock(request, "notifications.mako", "content",
                                        landing, "#next-load-wrapper", "replace",
                                        True, handlers={}, **args)
            else:
                yield renderScriptBlock(request, "notifications.mako", "content",
                                    landing, "#notifications", "set", **args)
    @defer.inlineCallbacks
    def _get_new_notifications(self, request):

        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        cols = yield Db.get_slice(myId, "latestNotifications")
        cols = utils.supercolumnsToDict(cols)
        counts = {myId: dict([(key, len(cols[key])) for key in cols])}
        orgId = args['orgKey']
        #get the list of groups
        cols = yield Db.get_slice(myId, "entities", ['adminOfGroups'])
        cols = utils.supercolumnsToDict(cols)
        groupIds = cols.get('adminOfGroups', {}).keys()

        if groupIds:
            cols = yield Db.multiget_slice(groupIds, "latestNotifications")
            cols = utils.multiSuperColumnsToDict(cols)
            for groupId in cols:
                counts[groupId] = {}
                for key in cols[groupId]:
                    counts[groupId][key] = len(cols[groupId][key])
        request.write(json.dumps(counts))


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        if segmentCount == 0:
            d = self._renderNotifications(request)
        elif segmentCount == 1 and request.postpath[0]=="new":
            d = self._get_new_notifications(request)
        return self._epilogue(request, d)
