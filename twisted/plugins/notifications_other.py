
from zope.interface     import implements
from twisted.plugin     import IPlugin

from social             import utils, brandName, rootUrl
from social             import template as t
from social.isocial     import INotificationType


class _SimpleNotification(object):
    notifyOnWeb = True

    def _render(self, parts, value, getTitle, getBody, data, args):
        args.update({'brandName': brandName, 'rootUrl': rootUrl})

        if getTitle:
            title = self._template[0] % args

        if getBody:
            args['senderAvatarUrl'] = utils.userAvatar(value,
                                                       data['entities'][value],
                                                       "medium")
            body = self._template[1] % args
            html = t.getBlock("emails.mako", self._template[2], **args)

        return (title, body, html)

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        args = {'senderName': data['entities'][value].basic['name']}
        if 'orgId' in data:
            orgId = data['orgId']
            args.update({'orgId': orgId,
                         'networkName': data['entities'][orgId].basic['name']})

        return self._render(parts, value, getTitle, getBody, data, args)

    def fetchAggregationData(self, parts, values):
        return (values, values, {})

    def aggregation(self, parts, values, data=None, fetched=None):
        userIds = utils.uniqify(values)
        noOfUsers = len(userIds)
        entities = data.get('entities', {})

        vals = dict([('user' + str(idx), utils.userName(uid, entities[uid]))\
                     for idx, uid in enumerate(userIds[0:2])])
        vals.update({'count': noOfUsers - 2, 'brandName': brandName})
        if 'org' in data:
            vals.update({'orgId': data['orgId'],
                         'networkName': data['org']['basic']['name']})

        return self._aggregation[3 if noOfUsers > 4 else noOfUsers - 1] % vals


class InviteAcceptedNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)
    notificationType = "IA"

    _template = [
        "%(senderName)s accepted your invitation to join %(brandName)s",
        "Hi,\n\n%(senderName)s accepted your invitation to join %(brandName)s",
        "notifyIA"
    ]

    _aggregation = [
        "%(user0)s accepted your invitation to join %(brandName)s",
        "%(user0)s and %(user1)s accepted your invitation to join %(brandName)s",
        "%(user0)s, %(user1)s and 1 other accepted your invitation to join %(brandName)s",
        "%(user0)s, %(user1)s and %(count)s others accepted your invitation to join %(brandName)s"
    ]


class NewUserNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)
    notificationType = "NU"

    _template = [
        "%(senderName)s joined the %(networkName)s network",
        "Hi,\n\n%(senderName)s joined the %(networkName)s network",
        "notifyNU"
    ]

    _aggregation = [
        "%(user0)s joined the %(networkName)s network",
        "%(user0)s and %(user1)s joined the %(networkName)s network",
        "%(user0)s, %(user1)s and 1 other joined the %(networkName)s network",
        "%(user0)s, %(user1)s and %(count)s others joined the %(networkName)s network"
    ]


class NewFollowerNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)
    notificationType = "NF"

    _template = [
        "%(senderName)s started following you",
        "Hi,\n\n%(senderName)s started following you",
        "notifyNF"
    ]

    _aggregation = [
        "%(user0)s started following you",
        "%(user0)s and %(user1)s started following you",
        "%(user0)s, %(user1)s and 1 other started following you",
        "%(user0)s, %(user1)s and %(count)s others started following you"
    ]


class KeywordNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)
    notificationType = "KW"

    _template = [
        "%(senderName)s posted content matching a keyword - %(keyword)s",
        "Hi,\n\n"\
            "%(senderName)s posted content that matched %(keyword)s.\n"\
            "Visit %(keywordUrl)s to see all conversations that matched this keyword.",
        "notifyKW"
    ]

    _aggregation = [
        "%(user0)s posted content that matched a keyword - %(keyword)s",
        "%(user0)s and %(user1)s posted content that matched a keyword - %(keyword)s",
        "%(user0)s and %(user1)s and 1 other posted content that matched a keyword - %(keyword)s",
        "%(user0)s and %(user1)s and %(count)s others posted content that matched a keyword - %(keyword)s"
    ]

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        args = {'senderName': data['entities'][value].basic['name'],
                'keyword': parts[2],
                'keywordUrl': '%s/admin/keyword-matches?keyword=%s' % (rootUrl, parts[2])}
        return self._render(parts, value, getTitle, getBody, data, args)

    def aggregation(self, parts, values, data=None, fetched=None):
        userIds = utils.uniqify(values)
        noOfUsers = len(userIds)
        entities = data.get('entities', {})

        keyword = parts[2]
        keyword = '<a class="ajax" href="/admin/keyword-matches?keyword=%s">%s</a>' % (keyword, keyword)

        vals = dict([('user' + str(idx), utils.userName(uid, entities[uid]))\
                     for idx, uid in enumerate(userIds[0:2])])
        vals.update({'count': noOfUsers - 2, 'brandName': brandName,
                     'keyword': keyword})

        return self._aggregation[3 if noOfUsers > 4 else noOfUsers - 1] % vals


class GroupNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)

    def __init__(self, notificationType):
        self.notificationType = notificationType
        self._template = getattr(self, '_template_' + notificationType)
        if notificationType == 'GR':
            self.notifyOnWeb = False
        else:
            self._aggregation = getattr(self, '_aggregation_' + notificationType)

    _template_GA = [
        "Your request to join %(senderName)s was accepted",
        "Hi,\n\nYour request to join %(senderName)s was accepted by an admistrator",
        "notifyGA"
    ]

    _template_GI = [
        "%(senderName)s invited you to join %(groupName)s",
        "Hi,\n\n"\
            "%(senderName)s invited you to join %(groupName)s group.\n"\
            "Visit %(rootUrl)s/groups?type=invitations to accept the invitation.",
        "notifyGI"
    ]

    _template_GR = [
        "%(senderName)s wants to join %(groupName)s",
        "Hi.\n\n"\
            "%(senderName)s wants to join %(groupName)s group\n"\
            "Visit %(rootUrl)s/groups?type=pendingRequests to accept the request",
        "notifyGR"
    ]

    _aggregation_GA = [
        "Your request to join %(group0)s was accepted",
        "Your requests to join %(group0)s and %(group1)s were accepted",
        "Your requests to join %(group0)s, %(group1)s and one other were accepted",
        "Your requests to join %(group0)s, %(group1)s and %(count)s others were accepted"
    ]

    _aggregation_GI = [
        "%(user0)s invited you to join %(group0)s",
        "%(user0)s and %(user1)s invited you to join %(group0)s",
        "%(user0)s and %(user1)s and 1 other invited you to join %(group0)s",
        "%(user0)s and %(user1)s and %(count)s others invited you to join %(group0)s"
    ]

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        if self.notificationType == "GA":
            args = {'senderName': data['entities'][value].basic['name']}
        else:
            args = {'senderName': data['entities'][value].basic['name'],
                    'groupName': data['groupName']}
        return self._render(parts, value, getTitle, getBody, data, args)

    def fetchAggregationData(self, parts, values):
        if self.notificationType == "GI":
            return (values, values + [parts[2]], {})
        else:
            return (values, values, {})

    def aggregation(self, parts, values, data=None, fetched=None):
        values = utils.uniqify(values)
        noOfUsers = len(values)
        entities = data.get('entities', {})

        if self.notificationType == "GI":
            vals = dict([('user' + str(idx), utils.userName(uid, entities[uid]))\
                         for idx, uid in enumerate(values[0:2])])
            groupId = parts[2]
            vals['group0'] = utils.groupName(groupId, entities[groupId])
        else:
            vals = dict([('group' + str(idx), utils.userName(uid, entities[uid]))\
                         for idx, uid in enumerate(values[0:2])])

        vals.update({'count': noOfUsers - 2, 'brandName': brandName})
        return self._aggregation[3 if noOfUsers > 4 else noOfUsers - 1] % vals


class MessageNotification(_SimpleNotification):
    implements(IPlugin, INotificationType)

    def __init__(self, notificationType):
        self.notificationType = notificationType
        self.notifyOnWeb = False
        self._template = getattr(self, '_template_' + notificationType)

    _template_NM = [
        "%(subject)s",
        "Hi,\n\n"\
            "%(senderName)s said - %(message)s\n\n"\
            "Visit %(convUrl)s to see the conversation",
        "notifyNM"
    ]

    _template_MR = [
        "Re: %(subject)s",
        "Hi,\n\n"\
            "%(senderName)s said - %(message)s\n\n"\
            "Visit %(convUrl)s to see the conversation",
        "notifyMR"
    ]

    _template_MA = [
        "Re: %(subject)s",
        "Hi,\n\n"\
            "%(senderName)s changed access controls of a message.\n"\
            "Visit %(convUrl)s to see the conversation",
        "notifyMA"
    ]

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        args = {'senderName': data['entities'][value].basic['name'],
                'convUrl': "%s/messages/thread?id=%s" % (rootUrl, data['convId']),
                'subject': data['subject'], 'message': data['message']}
        return self._render(parts, value, getTitle, getBody, data, args)


notifyInviteAccepted = InviteAcceptedNotification()
notifyNewUser = NewUserNotification()
notifyNewFollower = NewFollowerNotification()
notifyKeywordMatch = KeywordNotification()
notifyGroupAccept = GroupNotification("GA")
notifyGroupInvite = GroupNotification("GI")
notifyGroupRequest = GroupNotification("GR")
notifyNewMessage = MessageNotification("NM")
notifyMessageReply = MessageNotification("MR")
notifyMessageAccessChange = MessageNotification("MA")
