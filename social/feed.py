import time
import uuid

from twisted.internet   import defer
from twisted.web        import server

from social             import db, utils, base, plugins, _, __, errors, people
from social             import template as t
from social.core        import Feed
from social.isocial     import IAuthInfo, IFeedUpdateType
from social.relations   import Relation
from social.constants   import INFINITY, MAXFEEDITEMS, MAXFEEDITEMSBYTYPE
from social.constants   import SUGGESTION_PER_PAGE
from social.logging     import profile, dump_args, log

@defer.inlineCallbacks
def deleteUserFeed(userId, itemType, tuuid):
    yield db.remove(userId, "userItems", tuuid)
    if plugins.has_key(itemType) and plugins[itemType].hasIndex:
        yield db.remove(userId, "userItems_"+itemType, tuuid)


@defer.inlineCallbacks
def deleteFeed(userId, orgId, itemId, convId, itemType, acl, convOwner,
               responseType, others=None, tagId='', deleteAll=False):
    #
    # Wrapper around deleteFromFeed and deleteFromOthersFeed
    #
    yield deleteFromFeed(userId, itemId, convId, itemType,
                         userId, responseType, tagId )
    if deleteAll:
        yield deleteFromOthersFeed(userId, orgId, itemId, convId, itemType, acl,
                                   convOwner, responseType, others, tagId)


@profile
@defer.inlineCallbacks
@dump_args
def deleteFromFeed(userId, itemId, convId, itemType,
                   itemOwner, responseType, tagId=''):
    # fix: itemOwner is either the person who owns the item
    #       or person who liked the item. RENAME the variable.
    cols = yield db.get_slice(userId, "feedItems",
                              super_column=convId, reverse=True)

    noOfItems = len(cols)
    latest, second, pseudoFeedTime = None, None, None
    for col in cols:
        tuuid = col.column.name
        val = col.column.value
        rtype, poster, key =  val.split(":")[0:3]
        if latest and not second and rtype != "!":
            second = tuuid
        if not latest and rtype != "!":
            latest = tuuid
        if noOfItems == 2 and rtype == "!":
            pseudoFeedTime = tuuid

    cols = utils.columnsToDict(cols)

    for tuuid, val in cols.items():
        vals = val.split(":")
        rtype, poster, key =  val.split(":")[0:3]
        tag = ''
        if len(vals) == 5 and vals[4]:
            tag = vals[4]
        if rtype == responseType and \
            (rtype == "T" or poster == itemOwner) and \
            key == itemId and tagId == tag:
            # anyone can untag

            yield db.remove(userId, "feedItems", tuuid, convId)
            if latest == tuuid:
                yield db.remove(userId, "feed", tuuid)
                if second:
                    yield db.insert(userId, "feed", convId, second)
            if pseudoFeedTime:
                yield db.remove(userId, "feedItems", super_column=convId)
                yield db.remove(userId, "feed", pseudoFeedTime)
            if plugins.has_key(itemType) and plugins[itemType].hasIndex:
                yield db.remove(userId, "feed_"+itemType, tuuid)

            break


@profile
@defer.inlineCallbacks
@dump_args
def deleteFromOthersFeed(userId, orgId, itemId, convId, itemType, acl,
                         convOwner, responseType, others=None, tagId=''):
    if not others:
        others = yield utils.expandAcl(userId, orgId, acl, convId, convOwner)

    for key in others:
        yield deleteFromFeed(key, itemId, convId, itemType,
                             userId, responseType, tagId=tagId)


@profile
@defer.inlineCallbacks
@dump_args
def pushToOthersFeed(userKey, orgId, timeuuid, itemKey, parentKey, acl,
                     responseType, itemType, convOwner, others=None,
                     tagId='', entities=None, promoteActor=True):
    if not others:
        others = yield utils.expandAcl(userKey, orgId, acl, parentKey, convOwner)

    for key in others:
        promote = (userKey != key) or (promoteActor)
        yield pushToFeed(key, timeuuid, itemKey, parentKey,
                         responseType, itemType, convOwner,
                         userKey, tagId, entities, promote=promote)


@profile
@defer.inlineCallbacks
@dump_args
def pushToFeed(userKey, timeuuid, itemKey, parentKey, responseType,
               itemType, convOwner=None, commentOwner=None, tagId='',
               entities=None, promote=True):
    # Caveat: assume itemKey as parentKey if parentKey is None
    parentKey = itemKey if not parentKey else parentKey
    convOwner = userKey if not convOwner else convOwner
    commentOwner = userKey if not commentOwner else commentOwner

    # Get this conversation to the top of the feed only if promote is set
    if promote:
        yield db.insert(userKey, "feed", parentKey, timeuuid)
        if plugins.has_key(itemType) and plugins[itemType].hasIndex:
            yield db.insert(userKey, "feed_"+itemType, parentKey, timeuuid)

    yield updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                              responseType, convOwner, commentOwner, tagId,
                              entities, promote)


@profile
@defer.inlineCallbacks
@dump_args
def updateFeedResponses(userKey, parentKey, itemKey, timeuuid, itemType,
                        responseType, convOwner, commentOwner, tagId,
                        entities, promote):
    if not entities:
        entities = [commentOwner]
    else:
        entities.extend([commentOwner])
    entities = ",".join(entities)

    feedItemValue = ":".join([responseType, commentOwner, itemKey, entities, tagId])
    tmp, oldest, latest = {}, None, None

    cols = yield db.get_slice(userKey, "feedItems",
                              super_column=parentKey, reverse=True)
    cols = utils.columnsToDict(cols, ordered=True)

    feedKeys = []
    userFeedItems = []
    userFeedItemsByType = {}
    for tuuid, val in cols.items():
        # Bailout if we already know about this update.
        if tuuid == timeuuid:
            defer.returnValue(None)

        rtype = val.split(':')[0]
        if rtype not in  ('!', 'I'):
            tmp.setdefault(rtype, []).append(tuuid)
            if val.split(':')[1] == userKey:
                userFeedItems.append(tuuid)
                userFeedItemsByType.setdefault(rtype, []).append(tuuid)
            oldest = tuuid

        feedKeys.append(tuuid)

    # Remove older entries of this conversation from the feed
    # only if a new one was added before this function was called.
    if promote and feedKeys:
        yield db.batch_remove({'feed': [userKey]}, names=feedKeys)

    totalItems = len(cols)
    noOfItems = len(tmp.get(responseType, []))

    if noOfItems == MAXFEEDITEMSBYTYPE:
        if (len(userFeedItemsByType.get(responseType, {})) == MAXFEEDITEMSBYTYPE  and not promote)\
           or (tmp[responseType][noOfItems-1] not in userFeedItemsByType.get(responseType, {}) \
               and len(userFeedItemsByType.get(responseType, {})) == MAXFEEDITEMSBYTYPE-1 and not promote):
             oldest = userFeedItemsByType[responseType][noOfItems-2]
        else:
            oldest = tmp[responseType][noOfItems-1]

    if ((len(userFeedItems)== MAXFEEDITEMS-1 and not promote) or \
       (oldest not in userFeedItems and len(userFeedItems) == MAXFEEDITEMS-2 and not promote)):

        oldest = userFeedItems[-2]

    if noOfItems == MAXFEEDITEMSBYTYPE or totalItems == MAXFEEDITEMS:
        yield db.remove(userKey, "feedItems", oldest, parentKey)
        if plugins.has_key(itemType) and plugins[itemType].hasIndex:
            yield db.remove(userKey, "feed_"+itemType, oldest)

    if totalItems == 0 and responseType != 'I':
        value = ":".join(["!", convOwner, parentKey, ""])
        tuuid = uuid.uuid1().bytes
        yield db.batch_insert(userKey, "feedItems", {parentKey:{tuuid:value}})

    yield db.batch_insert(userKey, "feedItems",
                          {parentKey:{timeuuid: feedItemValue}})


class FeedResource(base.BaseResource):
    isLeaf = True
    resources = {}
    _templates = ['feed.mako']

    def paths(self):
        return  [('GET', '^/ui/share/(?P<typ>[^/]+)$', self.renderShareBlock),
                 ('GET', '^/(?P<entityId>[^/]*)$',     self.get)]

    def get(self, request, entityId=None):
        itemType = utils.getRequestArg(request, 'type')
        start = utils.getRequestArg(request, 'start') or ''
        more = utils.getRequestArg(request, 'more') or False

        if more:
            return self._renderMore(request, entityId, start, itemType)
        else:
            return self._render(request, entityId, start, itemType)

    @defer.inlineCallbacks
    def renderShareBlock(self, request, typ):
        plugin = plugins.get(typ, None)
        if plugin:
            yield plugin.renderShareBlock(request, self._ajax)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _render(self, request, entityId, start, itemType):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        itemType = utils.getRequestArg(request, 'type')
        start = utils.getRequestArg(request, "start") or ''

        landing = not self._ajax
        myOrgId = args["orgId"]

        feedTitle = _("News Feed")
        menuId = "feed"

        if entityId:
            entity = base.Entity(entityId)
            yield entity.fetchData(['basic', 'admins'])

            if not entity.basic:
                raise errors.InvalidEntity("feed", entityId)

            entityType = entity.basic['type']

            orgId = entity.basic["org"] if entityType != "org" else entityId

            if myOrgId != orgId:
                raise errors.EntityAccessDenied("organization", entityId)

            if entityType == 'org':
                menuId = "org"
                feedTitle = _("Company Feed: %s") % entity.basic["name"]
            elif entityType == 'group':
                request.redirect("/group?id=%s"%(entityId))
                defer.returnValue(None)
            elif entityId != myId:
                raise errors.EntityAccessDenied("user", entityId)

        feedId = entityId or myId
        args["feedTitle"] = feedTitle
        args["menuId"] = menuId
        args["feedId"] = feedId

        if script and landing:
            t.render(request, "feed.mako", **args)
            request.write('<script>$("#invite-form").html5form({messages: "en"})</script>')
        elif script and appchange:
            onload = '$("#invite-form").html5form({messages: "en"})'
            t.renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", handlers={'onload':onload}, **args)
        elif script and feedTitle:
            t.renderScriptBlock(request, "feed.mako", "feed_title",
                                landing, "#title", "set", True,
                                handlers={"onload": "$$.menu.selectItem('%s')"%(menuId)}, **args)

        if script:
            handlers = {}
            handlers["onload"] = handlers.get("onload", "") +\
                                 "$$.files.init('sharebar-attach');"
            t.renderScriptBlock(request, "feed.mako", "share_block",
                                landing, "#share-block", "set",
                                handlers=handlers, **args)
            yield self.renderShareBlock(request, "status")

        feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                   feedId=feedId, start=start,
                                   itemType=itemType)
        args.update(feedItems)
        args['itemType'] = itemType

        suggestions, entities = yield people.get_suggestions(request,
                                                SUGGESTION_PER_PAGE, mini=True)
        args["suggestions"] = suggestions

        if "entities" not in args:
            args["entities"] = entities
        else:
            for entityId in entities.keys():
                if entityId not in args["entities"].keys():
                    args["entities"][entityId] = entities[entityId]

        if script:
            onload = """
                        (function(obj){$$.convs.load(obj);})(this);
                        $('#feed-side-block-container').empty();
                     """
            t.renderScriptBlock(request, "feed.mako", "feed", landing,
                                "#user-feed", "set", True,
                                handlers={"onload": onload}, **args)
            t.renderScriptBlock(request, "feed.mako", "_suggestions",
                                landing, "#suggestions", "set", True, **args)

            for pluginType in plugins:
                plugin = plugins[pluginType]
                if hasattr(plugin, 'renderFeedSideBlock'):
                    if not entityId: entityId = myId
                    yield plugin.renderFeedSideBlock(request, landing,
                                                                 entityId, args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            t.render(request, "feed.mako", **args)

    # The client has scripts and this is an ajax request
    @defer.inlineCallbacks
    def _renderMore(self, request, entityId, start, itemType):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        entity = base.Entity(entityId)
        yield entity.fetchData()
        if entity.basic and entity.basic.get("type", '') == "group":
            errors.InvalidRequest("group feed will not be fetched.")

        feedItems = yield Feed.get(request.getSession(IAuthInfo),
                                   feedId=entityId, start=start,
                                   itemType=itemType)
        args.update(feedItems)
        args["feedId"] = entityId
        args['itemType'] = itemType

        onload = "(function(obj){$$.convs.load(obj);})(this);"
        t.renderScriptBlock(request, "feed.mako", "feed", False,
                            "#next-load-wrapper", "replace", True,
                            handlers={"onload": onload}, **args)

    @defer.inlineCallbacks
    def _renderChooseAudience(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)

        onload = "$('form').html5form({messages: 'en'});"
        t.renderScriptBlock(request, "feed.mako", "customAudience", False,
                            "#custom-audience-dlg", "set", True,
                            handlers={"onload": onload}, **args)

