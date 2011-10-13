import uuid
import time
import json

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server

from social             import base, db, utils, feed, settings
from social             import plugins, constants, _, config
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock, getBlock
from social.logging     import dump_args, profile, log

#
# Database schema for notifications
#
#     notifications (Standard CF):
#       Key: UserId
#       Column Name: TimeUUID
#       Column Value: NotifyId
#           (ConvId:ConvType:ConvOwner:X, :Y)
#               X => Type of action (Like/Comment/Like a comment)
#               Y => Type of action (Friend/Group/Following)
#
#     notificationItems (Super CF):
#       Key: UserId
#       Supercolumn Name: notifyId
#       Column Name: TimeUUID
#       Column Value: specific to type of notification
#           (Actor:ItemId, UserId, GroupId, UserId)
#

# Various notification handlers.
# Currently we only have a e-mail handler.
notificationHandlers = []

def notify(userIds, notifyId, value, timeUUID=None, **kwargs):
    if not userIds:
        return defer.succeed([])

    timeUUID = timeUUID or uuid.uuid1().bytes
    notifyIdParts = notifyId.split(':')
    deferreds = []

    # Delete existing notifications for the same item/activiy
    if not notifyIdParts[0] and notifyIdParts[1] not in ["FR", "GR", "NM", "MR", "MA"]:
        d1 = db.multiget_slice(userIds, "notificationItems",
                               super_column=notifyId, count=3, reverse=True)
        def deleteOlderNotifications(results):
            mutations = {}
            timestamp = int(time.time() * 10000000)
            for key, cols in results.iteritems():
                names = [col.column.name for col in cols
                                         if col.column.name != timeUUID]
                if names:
                    colmap = dict([(x, None) for x in names])
                    deletion = ttypes.Deletion(timestamp, 'notifications',
                                        ttypes.SlicePredicate(column_names=names))
                    mutations[key] = {'notifications': colmap,
                                      'latest': [deletion]}

            if mutations:
                return db.batch_mutate(mutations)
            else:
                return defer.succeed([])

        d1.addCallback(deleteOlderNotifications)
        deferreds.append(d1)

        # Create new notifications
        mutations = {}
        for userId in userIds:
            colmap = {timeUUID: notifyId}
            mutations[userId] = {'notifications': colmap,
                                 'latest': {'notifications': colmap},
                                 'notificationItems': {notifyId: {timeUUID: value}}}
        deferreds.append(db.batch_mutate(mutations))


    if notifyIdParts[0]:
        convId, convType, convOwner, notifyType = notifyIdParts
        for handler in notificationHandlers:
            d = handler.notifyConvUpdate(userIds, notifyType, convId, **kwargs)
            deferreds.append(d)
    else:
        for handler in notificationHandlers:
            d = handler.notifyOtherUpdate(userIds, notifyId, value, **kwargs)
            deferreds.append(d)

    return defer.DeferredList(deferreds)


#
# NotifcationByMail: Send notifications by e-mail
#
class NotificationByMail(object):

    _convNotifySubject = {
        "C": ["[%(brandName)s] %(senderName)s commented on your %(convType)s",
              "[%(brandName)s] %(senderName)s commented on %(convOwnerName)s's %(convType)s"],
        "L": ["[%(brandName)s] %(senderName)s liked your %(convType)s"],
        "T": ["[%(brandName)s] %(senderName)s tagged your %(convType)s as %(tagName)s"],
       "LC": ["[%(brandName)s] %(senderName)s liked your comment on your %(convType)s",
              "[%(brandName)s] %(senderName)s liked your comment on %(convOwnerName)s's %(convType)s"]

    }

    _convNotifyBody = {
        "C": ["Hi,\n\n"\
              "%(senderName)s commented on your %(convType)s.\n\n"\
              "%(senderName)s said - %(comment)s\n\n"\
              "See the full conversation at %(convUrl)s",
              "Hi,\n\n"\
              "%(senderName)s commented on %(convOwnerName)s's %(convType)s.\n\n"\
              "%(senderName)s said - %(comment)s\n\n"\
              "See the full conversation at %(convUrl)s"],
        "L": ["Hi,\n\n"\
              "%(senderName)s liked your %(convType)s.\n"\
              "See the full conversation at %(convUrl)s"],
        "T": ["Hi,\n\n"\
              "%(senderName)s tagged your %(convType)s as %(tagName)s.\n"\
              "See the full conversation at %(convUrl)s\n\n"\
              "You can see all items tagged %(tagName)s at %(tagFeedUrl)s]"],
       "LC": ["Hi,\n\n"\
              "%(senderName)s liked your comment on your %(convType)s.\n"\
              "See the full conversation at %(convUrl)s",
              "Hi,\n\n"\
              "%(senderName)s liked your comment on %(convOwnerName)s's %(convType)s.\n"\
              "See the full conversation at %(convUrl)s"]
    }

    _otherNotifySubject = {
        "IA": "[%(brandName)s] %(senderName)s accepted your invitation to join %(brandName)s",
        "NU": "[%(brandName)s] %(senderName)s joined the %(networkName)s network",
        "NF": "[%(brandName)s] %(senderName)s started following you",
        "FA": "[%(brandName)s] %(senderName)s accepted your friend request",
        "GA": "[%(brandName)s] Your request to join %(senderName)s was accepted",
        "GI": "[%(brandName)s] %(senderName)s invited you to join %(groupName)s",
        "FR": "[%(brandName)s] %(senderName)s wants to be your friend on %(networkName)s network",
        "GR": "[%(brandName)s] %(senderName)s wants to join %(groupName)s",
        "NM": "[%(brandName)s] %(senderName)s sent a private message",
        "MR": "[%(brandName)s] %(senderName)s sent a reply to private message",
        "MA": "[%(brandName)s] %(senderName)s changed access controls of a message"
    }

    _otherNotifyBody = {
        "IA": "Hi,\n\n"\
              "%(senderName)s accepted your invitation to join %(brandName)s",
        "NU": "Hi,\n\n"\
              "%(senderName)s joined the %(networkName)s network",
        "NF": "Hi,\n\n"\
              "%(senderName)s started following you",
        "FA": "Hi,\n\n"\
              "%(senderName)s accepted your friend request",
        "GA": "Hi,\n\n"\
              "Your request to join %(senderName)s was accepted by an admistrator",
        "GI": "Hi,\n\n"\
              "%(senderName)s invited you to join %(groupName)s group.\n"\
              "Visit %(rootUrl)s/groups?type=invitations to accept the invitation.",
        "FR": "Hi,\n\n"\
              "%(senderName)s requested to be your friend on %(networkName)s network.\n"\
              "To accept the request visit %(senderName)s's profile at %(rootUrl)s/profile?id=%(senderId)s.",
        "GR": "Hi.\n\n"\
              "%(senderName)s wants to join %(groupName)s group\n"\
              "Visit %(rootUrl)s/groups?type=pendingRequests to accept the request",
        "NM": "Hi,\n\n"\
              "%(senderName)s sent a message. \n"\
              "Vist the url to check the message: %(convUrl)s",
        "MR": "Hi, \n\n"\
              "%(senderName)s replied to a message. \n"\
              "Visit the url to check the message:  %(convUrl)s",
        "MA": "Hi, \n\n"\
              "%(senderName)s changed access controls of a message. \n"\
              "Visit the url to check the message: %(convUrl)s",
    }

    _signature = "\n\n"\
            "%(brandName)s Team.\n\n\n\n"\
            "--\n"\
            "Update your %(brandName)s notifications at %(rootUrl)s/settings?dt=notify\n"

    @defer.inlineCallbacks
    def notifyConvUpdate(self, recipients, notifyType, convId, **kwargs):
        rootUrl = config.get('General', 'URL')
        brandName = config.get('Branding', 'Name')

        # Local variables used to render strings
        me = kwargs["me"]
        myId = kwargs["myId"]
        senderName = me["basic"]["name"]
        convOwnerId = kwargs["convOwnerId"]
        entities = kwargs.get("entities", {})
        convOwnerName = entities[convOwnerId]["name"]
        stringCache = {}

        # Filter out users who don't need notification
        def needsNotifyCheck(userId):
            attr = 'notifyMyItem'+notifyType if convOwnerId == userId\
                                         else 'notifyItem'+notifyType
            user = entities[userId]
            return settings.getNotifyPref(user.get("notify", ''),
                            getattr(settings, attr), settings.notifyByMail)
        users = [x for x in recipients if needsNotifyCheck(x)]

        # Actually send the mail notification.
        def sendNotificationMail(followerId, data):
            toOwner = True if followerId == convOwnerId else False
            follower = entities[followerId]
            mailId = follower.get('emailId', None)
            if not mailId:
                return defer.succeed(None)

            # Sending to conversation owner
            if toOwner:
                s = self._convNotifySubject[notifyType][0] % data
                b = self._convNotifyBody[notifyType][0] + self._signature
                b = b % data
                h = getBlock("emails.mako",
                             "notifyOwner"+notifyType, **data)
                return utils.sendmail(mailId, s, b, h)

            # Sending to user other than conversation owner
            if 'subject' not in stringCache:
                s = self._convNotifySubject[notifyType][1] % data
                b = self._convNotifyBody[notifyType][1] + self._signature
                b = b % data
                h = getBlock("emails.mako", "notifyOther"+notifyType, **data)
                stringCache.update({'subject':s, 'text':b, 'html':h})

            return utils.sendmail(mailId, stringCache['subject'],
                                  stringCache['text'], stringCache['html'])

        data = kwargs.copy()
        convUrl = "%s/item?id=%s" % (rootUrl, convId)
        senderAvatarUrl = utils.userAvatar(myId, me, "medium")
        data.update({"senderName": senderName, "convUrl": convUrl,
                     "senderAvatarUrl": senderAvatarUrl, "rootUrl": rootUrl,
                     "brandName": brandName, "convOwnerName": convOwnerName})

        deferreds = []
        for userId in users:
            deferreds.append(sendNotificationMail(userId, data))

        yield defer.DeferredList(deferreds)


    # Sends the same message to all the recipients
    @defer.inlineCallbacks
    def notifyOtherUpdate(self, recipients, notifyId, value, **kwargs):
        rootUrl = config.get('General', 'URL')
        brandName = config.get('Branding', 'Name')

        notifyIdParts = notifyId.split(':')
        notifyType = notifyIdParts[1]

        entities = kwargs['entities']
        data = kwargs.copy()
        senderName = entities[value]['basic']['name']
        senderAvatarUrl = utils.userAvatar(value, entities[value], 'medium')

        if 'orgId' in data:
            orgId = data['orgId']
            data['networkName'] = entities[orgId]['basic']['name']

        data.update({'rootUrl': rootUrl, 'brandName': brandName,
                     'senderId': value, 'senderName': senderName,
                     'senderAvatarUrl': senderAvatarUrl})

        if notifyType in ['NM', 'MR', 'MA']:
            convId = data['convId']
            convUrl = "%s/messages/thread?id=%s" %(rootUrl, convId)
            data.update({"convUrl": convUrl})

        subject = self._otherNotifySubject[notifyType] % data
        body = self._otherNotifyBody[notifyType] + self._signature
        body = body % data
        html = getBlock("emails.mako", "notify"+notifyType, **data)

        # Sent the mail if recipient prefers to get it.
        deferreds = []
        prefAttr = getattr(settings, 'notify'+notifyType)
        prefMedium = settings.notifyByMail
        for userId in recipients:
            user = entities[userId]['basic']
            mailId = user.get('emailId', None)
            sendMail = settings.getNotifyPref(user.get("notify", ''),
                                              prefAttr, prefMedium)
            if sendMail and mailId:
                deferreds.append(utils.sendmail(mailId, subject, body, html))

        yield defer.DeferredList(deferreds)

notificationHandlers.append(NotificationByMail())



#
# NotificationResource: Display in-system notifications to the user
#
class NotificationsResource(base.BaseResource):
    isLeaf = True

    # String templates used in notifications.
    # Generally there are expected to be in past-tense since
    # notifications are record of something that already happened.
    _commentTemplate = {1: ["%(user0)s commented on your %(itemType)s",
                            "%(user0)s commented on %(owner)s's %(itemType)s"],
                        2: ["%(user0)s and %(user1)s commented on your %(itemType)s",
                            "%(user0)s and %(user1)s commented on %(owner)s's %(itemType)s"],
                        3: ["%(user0)s, %(user1)s and 1 other commented on your %(itemType)s",
                            "%(user0)s, %(user1)s and 1 other commented on %(owner)s's %(itemType)s"],
                        4: ["%(user0)s, %(user1)s and %(count)s others commented on your %(itemType)s",
                            "%(user0)s, %(user1)s and %(count)s others commented on %(owner)s's %(itemType)s"] }

    _answerTemplate = {1: ["%(user0)s answered your %(itemType)s",
                           "%(user0)s answered %(owner)s's %(itemType)s"],
                       2: ["%(user0)s and %(user1)s answered your %(itemType)s",
                           "%(user0)s and %(user1)s answered %(owner)s's %(itemType)s"],
                       3: ["%(user0)s, %(user1)s and 1 other answered your %(itemType)s",
                           "%(user0)s, %(user1)s and 1 other answered %(owner)s's %(itemType)s"],
                       4: ["%(user0)s, %(user1)s and %(count)s others answered your %(itemType)s",
                           "%(user0)s, %(user1)s and %(count)s others answered %(owner)s's %(itemType)s"] }

    _likesTemplate = {1: ["%(user0)s liked your %(itemType)s",
                          "%(user0)s liked %(owner)s's %(itemType)s"],
                      2: ["%(user0)s and %(user1)s liked your %(itemType)s",
                          "%(user0)s and %(user1)s liked %(owner)s's %(itemType)s"],
                      3: ["%(user0)s, %(user1)s and 1 other liked your %(itemType)s",
                          "%(user0)s, %(user1)s and 1 other liked %(owner)s's %(itemType)s"],
                      4: ["%(user0)s, %(user1)s and %(count)s others liked your %(itemType)s",
                          "%(user0)s, %(user1)s and %(count)s others liked %(owner)s's %(itemType)s"]}

    _answerLikesTemplate = {1: ["%(user0)s liked your answer on your %(itemType)s",
                                "%(user0)s liked your answer on %(owner)s's %(itemType)s"],
                            2: ["%(user0)s and %(user1)s liked your answer on your %(itemType)s",
                                "%(user0)s and %(user1)s liked your answer on %(owner)s's %(itemType)s"],
                            3: ["%(user0)s, %(user1)s and 1 other liked your answer on your %(itemType)s",
                                "%(user0)s, %(user1)s and 1 other liked your answer on %(owner)s's %(itemType)s"],
                            4: ["%(user0)s, %(user1)s and %(count)s others liked your answer on your %(itemType)s",
                                "%(user0)s, %(user1)s and %(count)s others liked your answer on %(owner)s's %(itemType)s"]}

    _commentLikesTemplate = {1: ["%(user0)s liked your comment on your %(itemType)s",
                                 "%(user0)s liked your comment on %(owner)s's %(itemType)s"],
                             2: ["%(user0)s and %(user1)s liked your comment on your %(itemType)s",
                                "%(user0)s and %(user1)s liked your comment on  %(owner)s's %(itemType)s"],
                             3: ["%(user0)s, %(user1)s and 1 other liked your comment on your %(itemType)s",
                                "%(user0)s, %(user1)s and 1 other liked your comment on %(owner)s's %(itemType)s"],
                             4: ["%(user0)s, %(user1)s and %(count)s others liked your comment on your %(itemType)s",
                                "%(user0)s, %(user1)s and %(count)s others liked your comment on %(owner)s's %(itemType)s"]}

    _inviteAccepted = {1: "%(user0)s accepted your invitation to join %(brandName)s",
                       2: "%(user0)s and %(user1)s accepted your invitation to join %(brandName)s",
                       3: "%(user0)s, %(user1)s and 1 other accepted your invitation to join %(brandName)s",
                       4: "%(user0)s, %(user1)s and %(count)s others accepted your invitation to join %(brandName)s"}

    _orgNewMember = {1: "%(user0)s joined the %(networkName)s network",
                     2: "%(user0)s and %(user1)s joined the %(networkName)s network",
                     3: "%(user0)s, %(user1)s and 1 other joined the %(networkName)s network",
                     4: "%(user0)s, %(user1)s and %(count)s others joined the %(networkName)s network"}

    _newFollowers = {1: "%(user0)s started following you",
                     2: "%(user0)s and %(user1)s started following you",
                     3: "%(user0)s, %(user1)s and 1 other started following you",
                     4: "%(user0)s, %(user1)s and %(count)s others started following you"}

    _friendRequestAccepted = {1: "%(user0)s accepted your friend request",
                              2: "%(user0)s and %(user1)s accepted your friend request",
                              3: "%(user0)s, %(user1)s and 1 other accepted your friend request",
                              4: "%(user0)s, %(user1)s and %(count)s others accepted your friend request"}

    _groupRequestAccepted = {1: "Your request to join %(group0)s was accepted",
                             2: "Your requests to join %(group0)s and %(group1)s were accepted",
                             3: "Your requests to join %(group0)s, %(group1)s and one other were accepted",
                             4: "Your requests to join %(group0)s, %(group1)s and %(count)s others were accepted"}

    _groupInvitation = {1: "%(user0)s invited you to join %(group0)s",
                        2: "%(user0)s and %(user1)s invited you to join %(group0)s",
                        3: "%(user0)s and %(user1)s and 1 other invited you to join %(group0)s",
                        4: "%(user0)s and %(user1)s and %(count)s others invited you to join %(group0)s"}

    #
    # Fetch notifications from the database
    # NotificationIds are stored in a column family called "notifications"
    #
    @defer.inlineCallbacks
    def _getNotifications(self, request, count=15):
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization

        nextPageStart = None
        keysFromStore = []      # List of keys fetched
        notifyIds = []          # convIds for which we have notifications
        details_d = []          # Deferreds waiting of notification items

        toFetchTags = set()
        toFetchEntities = set()
        tags = {}
        entities = {}
        timestamps = {}

        notifyStrs = {}
        notifyClasses = {}
        brandName = config.get('Branding', 'Name')

        fetchStart = utils.getRequestArg(request, 'start') or ''
        if fetchStart:
            fetchStart = utils.decodeKey(fetchStart)
        fetchCount = count + 2
        while len(notifyIds) < count:
            fetchedNotifyIds = []
            results = yield db.get_slice(myId, "notifications", count=fetchCount,
                                         start=fetchStart, reverse=True)
            for col in results:
                value = col.column.value
                if value not in notifyIds:
                    fetchedNotifyIds.append(value)
                    keysFromStore.append(col.column.name)
                    timestamps[value] = col.column.name

            if not keysFromStore:
                break

            fetchStart = keysFromStore[-1]
            notifyIds.extend(fetchedNotifyIds)

            if len(results) < fetchCount:
                break

            if len(keysFromStore) > count:
                nextPageStart = utils.encodeKey(keysFromStore[count])
                notifyIds = notifyIds[0:count]
            elif len(results) == fetchCount:
                nextPageStart = utils.encodeKey(keysFromStore[-1])
                notifyIds = notifyIds[0:-1]

        # We don't have notifications on any conversations
        if not notifyIds:
            defer.returnValue({})

        # We need the name of current user's organization
        toFetchEntities.add(myOrgId)

        # Fetch more data about the notifications
        notifyItems = yield db.get_slice(myId, "notificationItems",
                                         notifyIds, reverse=True)
        notifyValues = {}
        for notify in notifyItems:
            notifyId = notify.super_column.name
            notifyIdParts = notifyId.split(':')
            updates = notify.super_column.columns
            updates.reverse()
            notifyValues[notifyId] = []

            if notifyId.startswith(":"):    # Non-conversation updates
                # Currently, all notifications use only entities
                # We may have notifications that don't follow the same
                # symantics in future.  This is the place to fetch
                # any data required by such notifications.
                for update in updates:
                    toFetchEntities.add(update.value)
                    notifyValues[notifyId].append(update.value)
                if notifyIdParts[1] == 'GI':
                    toFetchEntities.add(notifyIdParts[2])

            elif len(notifyIdParts) == 4:   # Conversation updates
                convId, convType, convOwnerId, notifyType = notifyIdParts
                toFetchEntities.add(convOwnerId)
                for update in updates:
                    toFetchEntities.add(update.value.split(':')[0])
                    notifyValues[notifyId].append(update.value)

        # Fetch the required entities
        fetchedEntities = yield db.multiget_slice(toFetchEntities,
                                                  "entities", ["basic"])
        entities.update(utils.multiSuperColumnsToDict(fetchedEntities))
        myOrg = entities.get(myOrgId, {'basic': {'name':''}})

        # Build strings to notify actions on conversations
        def buildConvStr(notifyId):
            convId, convType, convOwnerId, notifyType = notifyId.split(':')

            userIds = utils.uniqify(notifyValues[notifyId])
            noOfUsers = len(userIds)

            vals = dict([('user'+str(idx), utils.userName(uid, entities[uid]))\
                            for idx, uid in enumerate(userIds[0:2])])

            vals["count"] = noOfUsers - 2

            # Limit noOfUsers to 4, to match with keys in template map
            noOfUsers = 4 if noOfUsers > 4 else noOfUsers
            if notifyType == "L":
                tmpl = self._likesTemplate[noOfUsers]
            elif notifyType == "C" and convType == "question":
                tmpl = self._answerTemplate[noOfUsers]
            elif notifyType == "C":
                tmpl = self._commentTemplate[noOfUsers]
            elif notifyType == "LC" and convType == "question":
                tmpl = self._answerLikesTemplate[noOfUsers]
            elif notifyType == "LC":
                tmpl = self._commentLikesTemplate[noOfUsers]

            # Strings change if current user owns the conversation
            tmpl = tmpl[0] if convOwnerId == myId else tmpl[1]

            vals["owner"] = utils.userName(convOwnerId, entities[convOwnerId])
            vals["itemType"] = utils.itemLink(convId, convType)
            return tmpl % vals

        # Build strings to notify all other actions
        def buildNotifyStr(notifyId):
            x = notifyId[1:]
            x = notifyId.split(':')[1]
            userIds = utils.uniqify(notifyValues[notifyId])
            noOfUsers = len(userIds)

            pfx = 'group' if x == 'GA' else 'user'
            if x == 'GA':
                vals = dict([(pfx+str(idx), utils.groupName(uid, entities[uid]))\
                            for idx, uid in enumerate(userIds[0:2])])
            else:
                vals = dict([(pfx+str(idx), utils.userName(uid, entities[uid]))\
                            for idx, uid in enumerate(userIds[0:2])])
            if x == 'GI':
                groupId = notifyId.split(':')[2]
                vals.update({'group0': utils.groupName(groupId, entities[groupId])})

            vals["count"] = noOfUsers - 2
            vals["brandName"] = brandName
            vals["networkName"] = myOrg['basic']['name']

            if noOfUsers > 4:
                noOfUsers = 4

            if x == "NF":
                tmpl = self._newFollowers[noOfUsers]
            elif x == "GA":
                tmpl = self._groupRequestAccepted[noOfUsers]
            elif x == "FA":
                tmpl = self._friendRequestAccepted[noOfUsers]
            elif x == "NU":
                tmpl = self._orgNewMember[noOfUsers]
            elif x == "IA":
                tmpl = self._inviteAccepted[noOfUsers]
            elif x == "GI":
                tmpl = self._groupInvitation[noOfUsers]

            return tmpl % vals

        # Build strings
        notifyStrs = {}
        for notifyId in notifyIds:
            if notifyId.startswith(":"):
                notifyStrs[notifyId] = buildNotifyStr(notifyId)
            else:
                notifyStrs[notifyId] = buildConvStr(notifyId)

        args = {"notifications": notifyIds,
                "notifyStr": notifyStrs,
                "notifyClasses": notifyClasses,
                "entities": entities,
                "nextPageStart": nextPageStart}
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
            yield db.remove(myId, "latest", super_column="notifications")

        args.update(data)
        if script:
            if fromFetchMore:
                yield renderScriptBlock(request, "notifications.mako", "content",
                                        landing, "#next-load-wrapper", "replace",
                                        True, handlers={}, **args)
            else:
                yield renderScriptBlock(request, "notifications.mako", "content",
                                    landing, "#notifications", "set", **args)
            yield utils.render_LatestCounts(request, landing)

    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self._renderNotifications(request)
        elif segmentCount == 1 and request.postpath[0] == "new" and self._ajax:
            d = utils.getLatestCounts(request)
            d.addCallback(lambda x: request.write('$$.menu.counts(%s);' % x))
        return self._epilogue(request, d)

