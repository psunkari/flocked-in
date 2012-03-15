import uuid
import time
import json

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.plugin     import getPlugins

from social             import base, db, utils, feed, settings
from social             import constants, _, config, brandName
from social             import template as t
from social.isocial     import IAuthInfo, INotificationType
from social.logging     import dump_args, profile, log

_notificationPlugins =  dict()
for plg in getPlugins(INotificationType):
    if not hasattr(plg, "disabled") or not plg.disabled:
        _notificationPlugins[plg.notificationType] = plg


#
# Database schema for notifications
#
#     notifications (Standard CF):
#       Key: UserId
#       Column Name: TimeUUID
#       Column Value: NotifyId
#           (ConvId:ConvType:ConvOwner:X, :Y)
#               X => Type of action (Like/Comment/Like a comment)
#               Y => Type of action (Group/Following)
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
    notifyType = notifyIdParts[1] if not notifyIdParts[0] else notifyIdParts[3]
    plugin = _notificationPlugins.get(notifyType, None)
    if not plugin:
        return defer.succeed([])

    deferreds = []

    # Delete existing notifications for the same item/activiy
    if plugin.notifyOnWeb:
        d1 = db.multiget_slice(userIds, "notificationItems",
                               super_column=notifyId, count=3, reverse=True)
        def deleteOlderNotifications(results):
            mutations = {}
            timestamp = int(time.time() * 1e6)
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


    for handler in notificationHandlers:
        d = handler.notify(userIds, notifyIdParts, value, **kwargs)
        deferreds.append(d)

    return defer.DeferredList(deferreds)


#
# NotifcationByMail: Send notifications by e-mail
#
class NotificationByMail(object):
    _signature = "\n\n"\
            "%(brandName)s Team.\n\n\n\n"\
            "--\n"\
            "Update your %(brandName)s notifications at %(rootUrl)s/settings?dt=notify\n"

    @defer.inlineCallbacks
    def notify(self, userIds, parts, value, **kwargs):
        isConvNotify = True if parts[0] else False
        if isConvNotify:
            yield self._notifyConvUpdate(userIds, parts, value, **kwargs)
        else:
            yield self.notifyOtherUpdate(userIds, parts, value, **kwargs)

    @defer.inlineCallbacks
    def _notifyConvUpdate(self, userIds, parts, value, **kwargs):
        convId, convType, convOwnerId, notifyType = parts
        plugin = _notificationPlugins.get(notifyType, None)
        if not plugin:
            return

        otherStringCache = []
        notifyAttrOwner = 'notifyMyItem' + notifyType
        notifyAttrOther = 'notifyItem' + notifyType
        entities = kwargs['entities']

        # Actually send the mail notification.
        def sendNotificationMail(followerId):
            toOwner = True if followerId == convOwnerId else False
            follower = entities[followerId]['basic']
            mailId = follower.get('emailId', None)
            if not mailId:
                return defer.succeed(None)

            # Sending to conversation owner
            if toOwner:
                if not settings.getNotifyPref(follower.get('notify', ''),
                                              getattr(settings, notifyAttrOwner),
                                              settings.notifyByMail):
                    return

                subject, body, html = plugin.render(parts, value,
                                                    toOwner=True, data=kwargs)
                subject = "[%s] %s" % (brandName, subject)

            # Sending to others
            else:
                if not settings.getNotifyPref(follower.get('notify', ''),
                                              getattr(settings, notifyAttrOther),
                                              settings.notifyByMail):
                    return

                if not otherStringCache:
                    subject, body, html = plugin.render(parts, value, data=kwargs)
                    subject = "[%s] %s" % (brandName, subject)
                    otherStringCache.extend([subject, body, html])

                subject, body, html = otherStringCache

            return utils.sendmail(mailId, subject, body, html)

        deferreds = []
        for userId in userIds:
            d = sendNotificationMail(userId)
            if d:
                deferreds.append(d)

        yield defer.DeferredList(deferreds)

    # Sends the same message to all the recipients
    @defer.inlineCallbacks
    def notifyOtherUpdate(self, recipients, parts, value, **kwargs):
        notifyType = parts[1]
        plugin = _notificationPlugins.get(notifyType, None)
        if not plugin:
            return

        subject, body, html = plugin.render(parts, value, data=kwargs)

        # Sent the mail if recipient prefers to get it.
        deferreds = []
        entities = kwargs['entities']
        prefAttr = getattr(settings, 'notify'+notifyType)
        prefMedium = settings.notifyByMail
        for userId in recipients:
            user = entities[userId]['basic']
            mailId = user.get('emailId', None)
            sendMail = settings.getNotifyPref(user.get("notify", ''),
                                              prefAttr, prefMedium)
            if sendMail and mailId:
                fromName = kwargs.get('_fromName', None) or 'Flocked-in'
                deferreds.append(utils.sendmail(mailId, subject,
                                                body, html, fromName=fromName))

        yield defer.DeferredList(deferreds)

notificationHandlers.append(NotificationByMail())


#
# NotificationResource: Display in-system notifications to the user
#
class NotificationsResource(base.BaseResource):
    isLeaf = True
    _templates = ['notifications.mako', 'emails.mako']

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
        notifyUsers = {}

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
                    timestamps[value] = col.column.timestamp/1e6

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
        notifyParts = {}
        notifyPlugins = {}
        notifyPluginData = {}
        for notify in notifyItems:
            notifyId = notify.super_column.name
            updates = notify.super_column.columns
            updates.reverse()
            notifyValues[notifyId] = []

            parts = notifyId.split(':')
            notifyType = parts[3] if parts[0] else parts[1]
            plugin = _notificationPlugins.get(notifyType, None)
            if not plugin:
                continue

            values = [update.value for update in updates]
            userIds, entityIds, pluginData = \
                    yield plugin.fetchAggregationData(parts, values)

            notifyValues[notifyId] = utils.uniqify(values)
            notifyParts[notifyId] = parts
            notifyPlugins[notifyId] = plugin
            notifyPluginData[notifyId] = pluginData
            notifyUsers[notifyId] = utils.uniqify(userIds)
            toFetchEntities.update(entityIds)

        # Fetch the required entities
        fetchedEntities = yield db.multiget_slice(toFetchEntities,
                                                  "entities", ["basic"])
        entities.update(utils.multiSuperColumnsToDict(fetchedEntities))
        myOrg = entities.get(myOrgId, {'basic': {'name':''}})

        # Build strings
        notifyStrs = {}
        data = {'entities': entities, 'myId': myId, 'orgId': myOrgId}
        for notifyId in notifyIds:
            parts = notifyParts.get(notifyId, None)
            if not parts:
                continue

            plugin = notifyPlugins[notifyId]
            notifyStrs[notifyId] = plugin.aggregation(parts,
                                            notifyValues[notifyId], data,
                                            notifyPluginData[notifyId])

        args = {"notifications": notifyIds, "notifyStr": notifyStrs,
                "notifyClasses": notifyClasses, "notifyUsers": notifyUsers,
                "entities": entities, "timestamps": timestamps,
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
            t.render(request, "notifications.mako", **args)

        if script and appchange:
            t.renderScriptBlock(request, "notifications.mako", "layout",
                                landing, "#mainbar", "set", **args)

        start = utils.getRequestArg(request, "start") or ''
        fromFetchMore = ((not landing) and (not appchange) and start)
        data = yield self._getNotifications(request)

        latest = yield db.get_slice(myId, "latest", super_column="notifications")
        latest = utils.columnsToDict(latest)
        latestNotifyIds = [x for x in latest.values()]

        if not start:
            yield db.remove(myId, "latest", super_column="notifications")

        args.update(data)
        args['latestNotifyIds'] = latestNotifyIds
        if script:
            if fromFetchMore:
                t.renderScriptBlock(request, "notifications.mako", "content",
                                    landing, "#next-load-wrapper", "replace",
                                    True, handlers={}, **args)
            else:
                t.renderScriptBlock(request, "notifications.mako", "content",
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

