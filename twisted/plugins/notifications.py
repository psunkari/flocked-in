
from zope.interface     import implements
from twisted.plugin     import IPlugin

from social             import utils, rootUrl
from social             import template as t
from social.isocial     import INotificationType


class CommentNotification(object):
    implements(IPlugin, INotificationType)
    notificationType = "C"
    notifyOnWeb = True

    # Comment notification sent to the owner of the conversation
    _toOwner_C = [
        "%(senderName)s commented on your %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s commented on your %(convType)s.\n\n"\
        "%(senderName)s said - %(comment)s\n\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOwnerC"  # Template method
    ]

    # Comment notification sent to everyone other than the
    # owner of the conversation
    _toOthers_C = [
        "%(senderName)s commented on %(convOwnerName)s's %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s commented on %(convOwnerName)s's %(convType)s.\n\n"\
        "%(senderName)s said - %(comment)s\n\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOtherC"
    ]

    # Aggregation of comment notifications on conversation
    _aggregation_C = [
        ["%(user0)s commented on your %(itemType)s",
         "%(user0)s commented on %(owner)s's %(itemType)s"],
        ["%(user0)s and %(user1)s commented on your %(itemType)s",
         "%(user0)s and %(user1)s commented on %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other commented on your %(itemType)s",
         "%(user0)s, %(user1)s and 1 other commented on %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others commented on your %(itemType)s",
         "%(user0)s, %(user1)s and %(count)s others commented on %(owner)s's %(itemType)s"]
    ]

    # Answer notification sent to the owner of the item
    _toOwner_A = [
        "%(senderName)s answered your question",
        "Hi,\n\n"\
        "%(senderName)s answered your question.\n\n"\
        "%(senderName)s said - %(comment)s\n\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOwnerA"
    ]

    # Answer notification sent to everyone other than the owner
    # of the Question
    _toOthers_A = [
        "%(senderName)s answered on %(convOwnerName)s's question",
        "Hi,\n\n"\
        "%(senderName)s answered on %(convOwnerName)s's question.\n\n"\
        "%(senderName)s said - %(comment)s\n\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOtherA"
    ]

    # Aggregation of all answer notifications on the conversation
    _aggregation_A = [
        ["%(user0)s answered your %(itemType)s",
         "%(user0)s answered %(owner)s's %(itemType)s"],
        ["%(user0)s and %(user1)s answered your %(itemType)s",
         "%(user0)s and %(user1)s answered %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other answered your %(itemType)s",
         "%(user0)s, %(user1)s and 1 other answered %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others answered your %(itemType)s",
         "%(user0)s, %(user1)s and %(count)s others answered %(owner)s's %(itemType)s"]
    ]

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        convId, convType, convOwnerId, notifyType = parts
        if convType == "question":
            templates = self._toOthers_A if not toOwner else self._toOwner_A
        else:
            templates = self._toOthers_C if not toOwner else self._toOwner_C

        title, body, html = '', '', ''
        senderName = data['me'].basic['name']
        convOwnerName = data['entities'][convOwnerId].basic['name']

        if getTitle:
            title = templates[0] % locals()

        if getBody:
            senderAvatarUrl = utils.userAvatar(data['myId'], data['me'], "medium")
            convUrl = "%s/item?id=%s" % (rootUrl, convId)

            comment = data.get('comment', '')
            body = templates[1] % locals()

            if 'richComment' in data:
                comment = data['richComment']

            vals = locals().copy()
            del vals['self']
            html = t.getBlock("emails.mako", templates[2], **vals)

        return (title, body, html)

    def fetchAggregationData(self, myId, orgId, parts, values):
        entityIds = [x.split(':')[0] for x in values]
        return (entityIds, entityIds + [parts[2]], {})

    def aggregation(self, parts, values, data=None, fetched=None):
        convId, convType, convOwnerId, notifyType = parts

        entities = data['entities']
        userCount = len(values)

        templates = self._aggregation_A if convType == "question"\
                                        else self._aggregation_C
        templatePair = templates[3 if userCount > 4 else userCount - 1]

        vals = dict([('user'+str(idx), utils.userName(uid, entities[uid]))\
                      for idx, uid in enumerate(values[0:2])])
        vals['count'] = userCount - 2
        vals['itemType'] = utils.itemLink(convId, convType)

        if convOwnerId == data['myId']:
            notifyStr = templatePair[0] % vals
        else:
            vals['owner'] = utils.userName(convOwnerId, entities[convOwnerId])
            notifyStr = templatePair[1] % vals

        return notifyStr


class LikeNotification(object):
    implements(IPlugin, INotificationType)
    notifyOnWeb = True

    # Notification when a conversation is liked
    _toOwner_L = [
        "%(senderName)s liked your %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s liked your %(convType)s.\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOwnerL"
    ]

    # Aggregation of all likes on a conversation
    _aggregation_L = [
        ["%(user0)s liked your %(itemType)s"],
        ["%(user0)s and %(user1)s liked your %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other liked your %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others liked your %(itemType)s"],
    ]

    # Notification about a comment being liked
    _toOwner_LC = [
        "%(senderName)s liked your comment on your %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s liked your comment on your %(convType)s.\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOwnerLC"
    ]

    # Notification about a comment liked on someone else's conversation
    _toOthers_LC = [
        "%(senderName)s liked your comment on %(convOwnerName)s's %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s liked your comment on %(convOwnerName)s's %(convType)s.\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOtherLC"
    ]

    # Aggregation of all likes on a comment
    _aggregation_LC = [
        ["%(user0)s liked your comment on your %(itemType)s",
         "%(user0)s liked your comment on %(owner)s's %(itemType)s"],
        ["%(user0)s and %(user1)s liked your comment on your %(itemType)s",
         "%(user0)s and %(user1)s liked your comment on  %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other liked your comment on your %(itemType)s",
         "%(user0)s, %(user1)s and 1 other liked your comment on %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others liked your comment on your %(itemType)s",
         "%(user0)s, %(user1)s and %(count)s others liked your comment on %(owner)s's %(itemType)s"]
    ]

    # Notification of an answer being liked
    _toOwner_LA = [
        "%(senderName)s liked your answer on your %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s liked your answer on your %(convType)s.\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOwnerLA"
    ]

    # Notification of an answer liked on someone else's conversation
    _toOthers_LA = [
        "%(senderName)s liked your answer on %(convOwnerName)s's %(convType)s",
        "Hi,\n\n"\
        "%(senderName)s liked your answer on %(convOwnerName)s's %(convType)s.\n"\
        "See the full conversation at %(convUrl)s",
        "notifyOtherLA"
    ]

    # Aggregation of all likes of the answer
    _aggregation_LA = [
        ["%(user0)s liked your answer on your %(itemType)s",
         "%(user0)s liked your answer on %(owner)s's %(itemType)s"],
        ["%(user0)s and %(user1)s liked your answer on your %(itemType)s",
         "%(user0)s and %(user1)s liked your answer on %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and 1 other liked your answer on your %(itemType)s",
         "%(user0)s, %(user1)s and 1 other liked your answer on %(owner)s's %(itemType)s"],
        ["%(user0)s, %(user1)s and %(count)s others liked your answer on your %(itemType)s",
         "%(user0)s, %(user1)s and %(count)s others liked your answer on %(owner)s's %(itemType)s"]
    ]

    def __init__(self, notificationType):
        self.notificationType = notificationType

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        convId, convType, convOwnerId, notifyType = parts
        if notifyType == "L":
            templates = self._toOthers_L if not toOwner else self._toOwner_L
        elif convType == "question":
            templates = self._toOthers_LA if not toOwner else self._toOwner_LA
        else:
            templates = self._toOthers_LC if not toOwner else self._toOwner_LC

        title, body, html = '', '', ''
        senderName = data['me'].basic['name']
        convOwnerName = data['entities'][convOwnerId].basic['name']

        if getTitle:
            title = templates[0] % locals()

        if getBody:
            senderAvatarUrl = utils.userAvatar(data['myId'], data['me'], "medium")
            convUrl = "%s/item?id=%s" % (rootUrl, convId)
            body = templates[1] % locals()

            vals = locals().copy()
            del vals['self']
            html = t.getBlock("emails.mako", templates[2], **vals)

        return (title, body, html)

    def fetchAggregationData(self, myId, orgId, parts, values):
        entityIds = [x.split(':')[0] for x in values]
        return (entityIds, entityIds + [parts[2]], {})

    def aggregation(self, parts, values, data=None, fetched=None):
        convId, convType, convOwnerId, notifyType = parts

        entities = data['entities']
        userCount = len(values)

        if notifyType == "L":
            templates = self._aggregation_L
        elif convType == "question":
            templates = self._aggregation_LA
        else:
            templates = self._aggregation_LC
        templatePair = templates[3 if userCount > 4 else userCount - 1]

        vals = dict([('user'+str(idx), utils.userName(uid, entities[uid]))\
                      for idx, uid in enumerate(values[0:2])])
        vals['count'] = userCount - 2
        vals['itemType'] = utils.itemLink(convId, convType)

        if convOwnerId == data['myId']:
            notifyStr = templatePair[0] % vals
        else:
            vals['owner'] = utils.userName(convOwnerId, entities[convOwnerId])
            notifyStr = templatePair[1] % vals

        return notifyStr


# TODO: Currently not being used.
class TagNotification(object):
    implements(IPlugin, INotificationType)
    notificationType = "T"
    notifyOnWeb = True

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        pass

    def aggregation(self, parts, values, data=None, fetched=None):
        pass


# TODO: Currently not being used.
class FlagNotification(object):
    implements(IPlugin, INotificationType)
    notifyOnWeb = True

    _itemFlaggedTemplate = {1: ["%(user0)s flagged your %(itemType)s for review"]}

    _itemRepliedFlaggedTemplate = {1: ["%(user0)s replied on your flagged %(itemType)s",
                                       "%(user0)s replied on the %(itemType)s that you flagged for review"]}

    _itemUnFlaggedTemplate = {1: ["%(user0)s restored your %(itemType)s"]}

    def __init__(self, notificationType):
        self.notificationType = notificationType

    def render(self, parts, value, toOwner=False,
               getTitle=True, getBody=True, data=None):
        pass

    def aggregation(self, parts, values, data=None, fetched=None):
        pass


notifyComment = CommentNotification()
notifyLike = LikeNotification("L")
notifyLikeComment = LikeNotification("LC")
notifyTag = TagNotification()
notifyFlag = FlagNotification("FC")
notifyUnflag = FlagNotification("UFC")
notifyFlagComment = FlagNotification("RFC")
