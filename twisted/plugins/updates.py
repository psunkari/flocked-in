
from zope.interface     import implements
from twisted.plugin     import IPlugin

from social             import utils
from social.isocial     import IFeedUpdateType


class CommentUpdate(object):
    implements(IPlugin, IFeedUpdateType)

    templates_C = [
        ["%(u0)s commented on your %(type)s",
         "%(u0)s commented on %(owner)s's %(type)s"],
        ["%(u0)s and %(u1)s commented on your %(type)s",
         "%(u0)s and %(u1)s commented on %(owner)s's %(type)s"],
        ["%(u0)s, %(u1)s and %(u2)s commented on your %(type)s",
         "%(u0)s, %(u1)s and %(u2)s commented on %(owner)s's %(type)s"]]

    templates_Q = [
        ["%(u0)s answered your %(type)s",
         "%(u0)s answered %(owner)s's %(type)s"],
        ["%(u0)s and %(u1)s answered your %(type)s",
         "%(u0)s and %(u1)s answered %(owner)s's %(type)s"],
        ["%(u0)s, %(u1)s and %(u2)s answered your %(type)s",
         "%(u0)s, %(u1)s and %(u2)s answered %(owner)s's %(type)s"]]

    def __init__(self, updateType="C"):
        self.updateType = updateType
        self.templates = getattr(self, 'templates_%s' % updateType)

    def parse(self, convId, updates):
        items = []
        entities = []
        for update in updates:
            if len(update) >= 3:
                (x, user, item) = update[0:3]
                items.append(item)
                entities.append(user)
        return (items, entities)

    def reason(self, convId, updates, data):
        entities = data['entities']
        meta = data['items'][convId]['meta']
        ownerId = meta['owner']
        myId = data['myId']

        uname = lambda x: utils.userName(x, entities[x], "conv-user-cause")
        users = utils.uniqify([x[1] for x in reversed(updates) if x[1] != myId])
        vals = dict([('u'+str(i), uname(x)) for i,x in enumerate(users)])
        vals.update({'owner':uname(ownerId),
                     'type':utils.itemLink(convId, meta['type'])})

        template = self.templates[len(users)-1][1] if ownerId != myId\
                   else self.templates[len(users)-1][0]
        return (template % vals, users)


class LikeUpdate(object):
    implements(IPlugin, IFeedUpdateType)

    templates_L = [
        ["%(u0)s liked your %(type)s",
         "%(u0)s liked %(owner)s's %(type)s"],
        ["%(u0)s and %(u1)s liked your %(type)s",
         "%(u0)s and %(u1)s liked %(owner)s's %(type)s"],
        ["%(u0)s, %(u1)s and %(u2)s liked your %(type)s",
         "%(u0)s, %(u1)s and %(u2)s liked %(owner)s's %(type)s"]]

    templates_LC = [
        ["%(u0)s liked a comment on your %(type)s",
         "%(u0)s liked a comment on %(owner)s's %(type)s"],
        ["%(u0)s and %(u1)s liked a comment on your %(type)s",
         "%(u0)s and %(u1)s liked a comment on %(owner)s's %(type)s"],
        ["%(u0)s, %(u1)s and %(u2)s liked a comment on your %(type)s",
         "%(u0)s, %(u1)s and %(u2)s liked a comment on %(owner)s's %(type)s"]]

    def __init__(self):
        self.updateType = "L"

    def parse(self, convId, updates):
        items = []
        entities = []
        for update in updates:
            if len(update) >= 4:
                (x, user, item, xtra) = update[0:4]
                entities.append(user)
                # XXX: We are not currently
                #      using this information anywhere.
                #      Bug #493
                #if item != convId:
                #    items.append(item)
                #    entities.extend(xtra.split(','))
        return (items, entities)

    def reason(self, convId, updates, data):
        likedItemId = updates[0][2]

        entities = data['entities']
        meta = data['items'][convId]['meta']
        ownerId = meta['owner']
        myId = data['myId']

        uname = lambda x: utils.userName(x, entities[x], "conv-user-cause")
        users = utils.uniqify([x[1] for x in reversed(updates) \
                               if x[1] != myId and x[2] == likedItemId])

        vals = dict([('u'+str(i), uname(x)) for i,x in enumerate(users)])
        vals.update({'owner':uname(ownerId),
                     'type':utils.itemLink(convId, meta['type'])})

        templates = self.templates_L if likedItemId == convId\
                                     else self.templates_LC
        template = templates[len(users)-1][1] if ownerId != myId\
                                        else templates[len(users)-1][0]
        return (template % vals, users)


class TagUpdate(object):
    implements(IPlugin, IFeedUpdateType)
    updateType = "T"

    templates = ["%(u0)s tagged your %(type)s as %(tag)s",
                 "%(u0)s tagged %(owner)s's %(type)s as %(tag)s"]

    def parse(self, convId, updates):
        for update in updates:
            if len(update) > 4 and update[4]:
                return ([], [update[1]])
        return ([], [])

    def reason(self, convId, updates, data):
        myId = data['myId']
        update = None

        for x in reversed(updates):
            if x[1] != myId and len(myId) > 4 and x[4]:
                update = x
                break
        if not update:
            return ('', [])

        tag = data.get('tags', {}).get(update[4], {}).get('title', '')
        if not tag:
            return ('', [])

        entities = data['entities']
        meta = data['items'][convId]['meta']
        ownerId = meta['owner']

        uname = lambda x: utils.userName(x, entities[x], "conv-user-cause")
        vals = {'u0': uname(update[1]), 'owner':uname(ownerId),
                'type':utils.itemLink(convId, meta['type']), 'tag': tag}

        template = self.templates[1] if ownerId != myId\
                                     else self.templates[0]
        return (template % vals, [update[1]])


commentUpdates = CommentUpdate("C")
answerUpdates = CommentUpdate("Q")
likeUpdates = LikeUpdate()
tagUpdates = TagUpdate()
