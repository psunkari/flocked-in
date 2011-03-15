import uuid
import time

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import base, Db, utils, feed, plugins, constants, _
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock


@defer.inlineCallbacks
def pushNotifications( itemId, convId, responseType,
                      convType, convOwner, commentOwner, timeUUID):

    # value = responseType:commentOwner:itemKey:convType:convOwner:
    value = ":".join([responseType, commentOwner, itemId, convType, convOwner])
    followers = yield Db.get_slice(convId, "items", super_column="followers")

    for follower in followers:
        userKey = follower.column.name
        if commentOwner != userKey:
            yield Db.insert(userKey, "notifications", convId, timeUUID)
            yield Db.batch_insert(userKey, "notificationItems", {convId:{timeUUID:value}})

@defer.inlineCallbacks
def deleteNofitications(convId, timeUUID):
    followers = yield Db.get_slice(convId, "items", super_column="followers")
    for follower in followers:
        userKey = follower.column.name
        yield Db.remove(userKey, "notifications", timeUUID)
        yield Db.remove(userKey, "notificationItems", timeUUID, convId)

class NotificationsResource(base.BaseResource):
    isLeaf = True


    @defer.inlineCallbacks
    def _getNotifications(self, userKey, count=10):

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
                vals.append(noOfUsers-3)
            vals.append(utils.userName(itemOwnerId, users[itemOwnerId]))
            vals.append(utils.itemLink(convId, itemType))
            return _(template) %(tuple(vals))

        args = {}
        convs = []
        start = ""
        comments = {}
        reasonStr = {}
        convLikes = {}
        commentLikes = {}
        toFetchUsers = set()
        toFetchGroups = set()
        fetchCount = count + 5

        while len(convs) < count:
            cols = yield Db.get_slice(userKey, "notifications", count=fetchCount,
                                      start=start, reverse=True)
            for col in cols:
                value = col.column.value
                if value not in convs:
                    convs.append(value)
            if len(cols) < fetchCount:
                break
            start = cols[-1].column.name

        args["conversations"] = convs
        if not convs:
            defer.returnValue(args)


        rawNotifications = yield Db.get_slice(userKey, "notificationItems",
                                              convs, reverse=True)
        rawNotifications = utils.supercolumnsToDict(rawNotifications)
        for convId in rawNotifications:
            for timeUUID, value in rawNotifications[convId].items():
                responseType, commentOwner, itemId,\
                                convType, convOwner = value.split(":")
                key = (convId, convType, convOwner)
                toFetchUsers.add(commentOwner)
                toFetchUsers.add(convOwner)
                if responseType == "C":
                    comments.setdefault(key, [])
                    comments[key].append(commentOwner)
                elif responseType == "L" and itemId == convId:
                    convLikes.setdefault(key, [])
                    convLikes[key].append(commentOwner)
                elif responseType == "L" and itemId != convId:
                    commentLikes.setdefault(key, [])
                    commentLikes[key].append(commentOwner)

        users = yield Db.multiget_slice(toFetchUsers, "users", ["basic"])
        groups = yield Db.multiget_slice(toFetchGroups, "groups", ["basic"])

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

        for convId in convs:
            reasonStr[convId] = []

        for key in comments:
            convId, convType, convOwner = key
            template = commentTemplate[len(set(comments[key]))]
            reason = _getReasonStr(template, convId, convType, convOwner, comments[key])
            reasonStr[convId].append(reason)
        for key in convLikes:
            convId, convType, convOwner = key
            template = likesTemplate[len(set(convLikes[key]))]
            reason = _getReasonStr(template, convId, convType, convOwner, convLikes[key])
            reasonStr[convId].append(reason)
        for key in commentLikes:
            convId, convType, convOwner = key
            template = commentLikesTemplate[len(set(commentLikes[key]))]
            reason = _getReasonStr(template, convId, convType, convOwner, commentLikes[key])
            reasonStr[convId].append(reason)

        args["reasonStr"] = reasonStr
        args["groups"] = groups
        args["users"] = users

        defer.returnValue(args)

    @defer.inlineCallbacks
    def _renderNotifications(self, request):

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        if script and landing:
            yield render(request, "notifications.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "notifications.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        data = yield self._getNotifications(myKey)
        args.update(data)

        if script:
            yield renderScriptBlock(request, "notifications.mako", "content",
                                    landing, "#center", "set", **args)


    def render_GET(self, request):
        d = self._renderNotifications(request)
        def callback(res):
            request.finish()
        def errback(err):
            log.msg(err)
            request.finish()
        d.addCallbacks(callback, errback)
        return server.NOT_DONE_YET
