import time
import re
from base64                     import urlsafe_b64decode
from lxml                       import etree
from lxml.builder               import ElementMaker
from zope.interface             import implements
from urllib                     import quote, unquote
from markdown                   import markdown
try:
    import cPickle as pickle
except:
    import pickle

from twisted.web                import client
from twisted.web.iweb           import IBodyProducer
from twisted.internet           import protocol, reactor, defer
from twisted.web.http           import PotentialDataLoss
from twisted.web.http_headers   import Headers

from social                     import base, utils, config, feed
from social                     import errors, plugins, _, db
from social.constants           import SEARCH_RESULTS_PER_PAGE
from social.template            import render, renderScriptBlock
from social.logging             import dump_args, profile, log
from social.relations           import Relation


URL = config.get('SOLR', 'HOST')


class XMLBodyProducer(object):
    implements (IBodyProducer)

    def __init__(self, domtree):
        self._body = etree.tostring(domtree)
        self.length = len(self._body)

    def startProducing(self, consumer):
        consumer.write(self._body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class PythonBodyReceiver(protocol.Protocol):
    def __init__(self, deferred):
        self._deferred = deferred
        self.data = ''

    def dataReceived(self, data):
        self.data += data

    def connectionLost(self, reason):
        if not self._deferred:
            return

        if reason.check(client.ResponseDone, PotentialDataLoss):
            self.data = eval(self.data)
            self._deferred.callback(self)
        else:
            self._deferred.errback(reason)


def _toUnicodeOrText(text):
    if isinstance(text, str):
        return text.decode('utf8', 'replace')
    elif isinstance(text, unicode):
        return text
    else:
        return str(text)


class Solr(object):
    def __init__(self):
        self._updateURL = URL + "/update?commit=true"
        self._headers = {}
        self.elementMaker = ElementMaker()

    def _request(self, method, url, headers=None, producer=None):
        if URL:
            allHeaders = self._headers
            if headers:
                allHeaders.update(headers)
            agent = client.Agent(reactor)
            return agent.request(method, url, Headers(allHeaders), producer)
        else:
            return defer.succeed(None)


    def updatePeopleIndex(self, myId, me, orgId):
        mailId = me['basic']['emailId']
        fields = [self.elementMaker.field(myId, {"name":"id"}),
                  self.elementMaker.field(orgId, {"name":"org"}),
                  self.elementMaker.field('people', {"name":"_type"}),
                  self.elementMaker.field(mailId, {'name':'email'}) ]

        for field in ['name', 'lastname', 'firstname', 'jobTitle']:
            if field in me['basic']:
                fields.append(self.elementMaker.field(_toUnicodeOrText(me['basic'][field]), {'name': field}))

        for field in ['phone', 'mobile']:
            if field in me.get('contact', {}):
                fields.append(self.elementMaker.field(_toUnicodeOrText(me['contact'][field]), {'name': field}))

        for field in ['email', 'phone', 'mobile', 'currentCity']:
            if field in me.get('personal', {}):
                fields.append(self.elementMaker.field(_toUnicodeOrText(me['personal'][field]), {'name': field}))

        schools = set()
        for school in me.get('schools', {}).keys():
            year, name = school.split(':', 1)
            schools.add(name)
        fields.extend([self.elementMaker.field(_toUnicodeOrText(x), {'name': 'school'}) for x in schools])

        companies = set()
        for company in me.get('companies', {}).keys():
            end, start, name = company.split(':', 2)
            companies.add(name)
        fields.extend([self.elementMaker.field(_toUnicodeOrText(x), {'name': 'company'}) for x in companies])

        skills = ','.join(me.get('expertise', {}).keys())
        if skills:
            fields.append(self.elementMaker.field(_toUnicodeOrText(skills), {'name': 'expertise'}))

        fields.append(self.elementMaker.field(str(int(time.time())), {'name': 'timestamp'}))

        avatarURI = utils.userAvatar(myId, me, 'small')
        fields.append(self.elementMaker.field(avatarURI, {'name': 'avatar'}))

        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        return self._request("POST", self._updateURL, {}, XMLBodyProducer(root))


    def _getAttachmentFields(self, attachments):
        fields = []
        for attachId in attachments.keys():
            timeUUID, name, size, fileType = attachments[attachId].split(':')
            name = _toUnicodeOrText(urlsafe_b64decode(name))
            fields.append(self.elementMaker.field("%s:%s"%(attachId, name, {'name': 'attachment'}))
        return fields


    def updateMessageIndex(self, itemId, item, orgId):
        fields = [self.elementMaker.field(itemId, {"name":"id"}),
                  self.elementMaker.field(orgId, {"name":"org"}),
                  self.elementMaker.field('message', {"name":"_type"})]

        meta = item.get('meta', {})
        for name in ['subject', 'body', 'parent']:
            value = meta.get(name, None)
            if value:
                value = value.decode('utf-8', 'replace')
                fields.append(self.elementMaker.field(value, {"name": name}))

        if 'attachments' in item:
            fields.extend(self._getAttachmentFields(item['attachments']))

        if 'timestamp' in meta and meta['timestamp']:
            fields.append(self.elementMaker.field(meta['timestamp'], {"name": "timestamp"}))

        participants = item.get('participants', {})
        for user in participants:
            fields.append(self.elementMaker.field(user, {"name": "participant"}))

        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        return self._request("POST", self._updateURL, {}, XMLBodyProducer(root))


    def updateItemIndex(self, itemId, item, orgId, conv=None):
        fields = [self.elementMaker.field(itemId, {"name":"id"}),
                  self.elementMaker.field(orgId, {"name":"org"}),
                  self.elementMaker.field('item', {"name":"_type"})]

        meta = item.get('meta', {})
        parentId = meta.get('parent', None)
        richText = meta.get('richText', 'False') == 'True'

        indexFields = {'meta':set(['comment','parent','type'])}

        if parentId:
            convMeta = conv.get('meta', {}) if conv else {}
        else:
            itemType = meta.get('type', 'status')
            if itemType in plugins:
                pluginIndexFields = getattr(plugins[itemType], "indexFields", {})
                for key, value in pluginIndexFields.items():
                    if key not in indexFields:
                        indexFields[key] = value
                    else:
                        indexFields[key].update(value)

        for superColName, columnNames in indexFields.items():
            if isinstance(columnNames, set):
                for columnName in columnNames:
                    value = item.get(superColName, {}).get(columnName, None)
                    if value:
                        if columnName == 'comment' and richText:
                            value = utils.richTextToText(value)
                        if isinstance(value, str):
                            value = value.decode('utf-8', 'replace')
                        elif not isinstance(value, unicode):
                            value = str(value)

                        fields.append(self.elementMaker.field(value, {"name":columnName}))
            elif isinstance(columnNames, dict) and not parentId:
                indexType = columnNames.get('type', 'keyval')
                indexTmpl = columnNames.get('template', '')
                if indexType == "keyvals":
                    if not indexTmpl:
                        indexTmpl = itemType + "_" + superColumnName + "_%s"
                    for key, val in item.get(superColName, {}).items():
                        fields.append(self.elementMaker.field(val, {"name": indexTmpl % key}))
                elif indexType == "multikeys":
                    if not indexTmpl:
                        indexTmpl = itemType + "_" + superColumnName
                    for key in item.get(superColName, {}).keys():
                        fields.append(self.elementMaker.field(key, {"name": indexTmpl}))
                elif indexType == "multivals":
                    if not indexTmpl:
                        indexTmpl = itemType + "_" + superColumnName
                    for val in item.get(superColName, {}).values():
                        fields.append(self.elementMaker.field(val, {"name": indexTmpl}))

        if 'attachments' in item:
            fields.extend(self._getAttachmentFields(item['attachments']))

        acl = meta.get('acl', None) if not parentId else convMeta.get('acl', None)
        acl = pickle.loads(acl) if acl else {}
        for denied in acl.get('deny', {}).values():
            fields.extend([self.elementMaker.field(x, {"name":"_denyACL"}) for x in denied])
        for allowed in acl.get('accept', {}).values():
            fields.extend([self.elementMaker.field(x, {"name":"_acceptACL"}) for x in allowed])

        if "timestamp" in meta:
            fields.append(self.elementMaker.field(meta['timestamp'], {"name":"timestamp"}))

        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        return self._request("POST", self._updateURL, {}, XMLBodyProducer(root))


    def delete(self, uniqueId):
        root = self.elementMaker.delete(self.elementMaker.id(str(uniqueId)))
        return self._request("POST", self._updateURL, {}, XMLBodyProducer(root))


    def search(self, term, orgId, count, start=0, filters=None):
        def callback(response):
            finished = defer.Deferred()
            response.deliverBody(PythonBodyReceiver(finished))
            return finished
        term = quote(term)
        url = URL + "/select?wt=python&q=%s&start=%s&rows=%s&sort=%s&hl=true&hl.fl=*&fq=org:%s" \
                    % (term, start, count, quote('timestamp desc'), orgId)
        if filters:
            for x in filters:
                url += '&fq=%s:%s' %(x, quote(filters[x]))
        d = self._request("GET", url)
        d.addCallback(callback)
        return d


class SearchResource(base.BaseResource):
    isLeaf = True

    TYPE_ITEMS = 1
    TYPE_PEOPLE = 2
    TYPE_GROUPS = 4
    TYPE_TAGS = 8
    TYPE_MESSAGES = 16
    itemTypes = {'items': TYPE_ITEMS, 'people': TYPE_PEOPLE,
                 'groups': TYPE_GROUPS, 'tags': TYPE_TAGS,
                 'messages': TYPE_MESSAGES}

    @defer.inlineCallbacks
    def search(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']

        term = utils.getRequestArg(request, "q")
        if not term:
            errors.MissingParams(['Search term'])
        args["term"] = term

        itemType = utils.getRequestArg(request, "it") or 0
        try:
            itemType = int(itemType)
            if not 0 < itemType < 31:
                raise ValueError
        except ValueError:
            itemType = self.TYPE_ITEMS | self.TYPE_PEOPLE
        args["itemType"] = itemType

        start = utils.getRequestArg(request, "start") or 0
        try:
            start = int(start)
            if start < 0:
                raise ValueError
        except ValueError:
            start = 0
        args["start"] = start

        if script  and landing:
            yield render(request, "search.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "search.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        toFetchEntities = set()
        toFetchItems = set()
        toFetchTags = set()
        deferreds = []
        highlight = {}

        # If searching for more than one itemType then use half the count.
        count = SEARCH_RESULTS_PER_PAGE if itemType in [1,2,4,8,16] else SEARCH_RESULTS_PER_PAGE/2

        relation = Relation(myId, [])
        relation_d = relation.initGroupsList()
        args['relations'] = relation

        people = {}
        args['matchedUsers'] = people
        if itemType & self.TYPE_PEOPLE:
            d = solr.search(term, myOrgId, count, start, filters={'_type':'people'})
            def _gotPeople(results):
                docs = results.data.get('response', {}).get('docs', [])
                highlight.update(results.data.get('highlighting'))
                for item in docs:
                    entityId = item['id']
                    people[entityId] = item
                args['matchedUserCount'] = results.data.get('response', {}).get('numFound', 0)
            d.addCallback(_gotPeople)
            deferreds.append(d)

        items = {}
        matchedItemIds = []
        args['items'] = items
        args['matchedItemIds'] = matchedItemIds
        if itemType & self.TYPE_ITEMS:
            yield relation_d
            aclFilterEntities = relation.groups + [myOrgId, myId]
            filters = {'_type': 'item',
                       '_acceptACL': '(%s)' % ' OR '.join(aclFilterEntities),
                       '-_denyACL': '(%s)' % ' OR '.join(aclFilterEntities)}
            d = solr.search(term, myOrgId, count, start, filters=filters)

            @defer.inlineCallbacks
            def _gotConvs(results):
                docs = results.data.get('response', {}).get('docs', [])
                highlight.update(results.data.get('highlighting'))
                for index, item in enumerate(docs):
                    itemId = item['id']
                    parentId = item.get('parent', None)
                    if parentId:
                        toFetchItems.add(itemId)
                        toFetchItems.add(parentId)
                        matchedItemIds.append(itemId)
                    else:
                        toFetchItems.add(itemId)
                        matchedItemIds.append(itemId)

                if toFetchItems and matchedItemIds:
                    fetchedItems = yield db.multiget_slice(toFetchItems,
                                    "items", ["meta", "tags", "attachments"])
                    fetchedItems = utils.multiSuperColumnsToDict(fetchedItems)
                    for itemId, item in fetchedItems.items():
                        toFetchEntities.add(item['meta']['owner'])
                        if 'target' in item['meta']:
                            toFetchEntities.update(item['meta']['target'].split(','))

                    items.update(fetchedItems)

                extraDataDeferreds = []
                for itemId in toFetchItems:
                    if itemId in matchedItemIds and itemId in items:
                        meta = items[itemId]['meta']
                        itemType = meta.get('type', 'status')
                        if itemType in plugins:
                            d = plugins[itemType].fetchData(args, itemId)
                            extraDataDeferreds.append(d)

                result = yield defer.DeferredList(extraDataDeferreds)
                for success, ret in result:
                    if success:
                        toFetchEntities.update(ret)
                args['matchedItemCount'] = results.data.get('response', {}).get('numFound', 0)

            d.addCallback(_gotConvs)
            deferreds.append(d)

        yield defer.DeferredList(deferreds)
        entities = {}
        args['entities'] = entities
        if toFetchEntities:
            fetchedEntities = yield db.multiget_slice(toFetchEntities,
                                                      "entities", ["basic"])
            fetchedEntities = utils.multiSuperColumnsToDict(fetchedEntities)
            entities.update(fetchedEntities)

        tags = {}
        args['tags'] = tags
        if toFetchTags:
            fetchedTags = yield db.get_slice(myOrgId, "orgTags", toFetchTags)
            tags.update(utils.supercolumnsToDict(fetchedTags))

        args['highlight'] = highlight
        if script:
            yield renderScriptBlock(request, "search.mako", "results",
                                    landing, "#search-results", "set", **args)
        else:
            yield render(request, "search.mako", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _search(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']
        filter_map = {'people':'itemType'}

        term = utils.getRequestArg(request, "q")
        start = utils.getRequestArg(request, "start") or 0
        filters = utils.getRequestArg(request, 'filter', multiValued=True) or []
        filters = dict([(filter_map[x], x) for x in filters if x in filter_map])
        args["term"] = term
        nextPageStart = ''

        if not term:
            errors.MissingParams()

        try:
            start = int(start)
            if start < 0:
                raise ValueError
        except ValueError:
            errors.InvalidParamValue()

        if script  and landing:
            yield render(request, "search.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "search.mako", "layout",
                                    landing, "#mainbar", "set", **args)
        count = SEARCH_RESULTS_PER_PAGE
        items = {}
        convs = set()
        highlighting = {}
        toFetchItems = []
        toFetchStart = start
        toFetchEntities = set()
        people = []
        relation = Relation(myId, [])
        yield defer.DeferredList([relation.initGroupsList(),
                                  relation.initSubscriptionsList(),
                                  relation.initFollowersList()])
        regex = re.compile("(.*?)([^\s]*\s*[^\s]*\s*[^\s]*\s*)(<em class='highlight'>.*<\/em>)(\s*[^\s]*\s*[^\s]*\s*[^\s]*)(.*)")

        res = yield solr.search(term, args['orgKey'], count, toFetchStart, filters={'itemType': 'people'})
        docs = res.data.get('response', {}).get('docs', [])
        for item in docs:
            entityId = item['id']
            people.append(entityId)
            toFetchEntities.add(entityId)

        while 1:
            res = yield solr.search(term, args['orgKey'], count, toFetchStart)
            messages = []
            convItems = []
            numMatched = res.data.get('response', {}).get('numFound', 0)
            docs = res.data.get('response', {}).get('docs', [])
            highlighting.update(res.data.get('highlighting', {}))
            for index, item in enumerate(docs):
                itemId = item['id']
                parent = item.get('parent', None)
                position = toFetchStart + index
                if item.get('itemType', '') == "message":
                    if (item.get('id'), parent) not in messages:
                        messages.append((item.get('id'), parent))
                elif item.get('itemType', '') == 'people':
                    entityId = item.get('id')
                    if entityId not in people:
                        people.append(entityId)
                        toFetchEntities.add(entityId)
                elif parent:
                    convItems.append((itemId, parent, position))
                    convs.add(parent)
                else:
                    convItems.append((itemId, itemId, position))
                    convs.add(item.get('id'))
            if convs:
                filteredConvs, deleted  = yield feed.fetchAndFilterConvs(convs, count, relation, items, myId, myOrgId)
                for itemId, convId, position in convItems:
                    if convId in filteredConvs and itemId not in toFetchItems:
                        toFetchItems.append(itemId)
                    if len(toFetchItems) == count:
                        if position +1 < numMatched:
                            nextPageStart = position + 1
                        break
            if len(toFetchItems) == count or len(docs) < count:
                break
            toFetchStart = toFetchStart + count

        _items = yield db.multiget_slice(toFetchItems, "items",
                                           ['meta', 'attachments', 'tags'])
        items.update(utils.multiSuperColumnsToDict(_items))
        for itemId, item in items.iteritems():
            toFetchEntities.add(item['meta']['owner'])
            if 'target' in item['meta']:
                toFetchEntities.update(item['meta']['target'].split(','))
            if itemId in highlighting and 'comment' in highlighting[itemId]:
                match = re.match(regex, unquote(highlighting[itemId]['comment'][0]))
                if match:
                    comment = "".join(match.groups()[1:4])
                    comment = comment + " &hellip;" if match.group(5) else comment
                    items[itemId]['meta']['comment'] = comment

        entities = yield db.multiget_slice(toFetchEntities, "entities", ['basic'])
        entities = utils.multiSuperColumnsToDict(entities)

        for userId in people:
            if userId in highlighting and userId in entities:
                entities[userId]['basic']['reason'] = {}
                for key in highlighting[userId]:
                    if key in entities[userId]['basic']:
                        entities[userId]['basic'][key] = " ".join(highlighting[userId][key])
                    else:
                        entities[userId]['basic']['reason'][key] = highlighting[userId][key]

        fromFetchMore = True if start else False
        args['term'] = term
        args['items'] = items
        args['people'] = people
        args['entities'] = entities
        args['relations'] = relation
        args["conversations"] = toFetchItems
        args["nextPageStart"] = nextPageStart
        args['fromFetchMore'] = fromFetchMore
        args['fromSidebar'] = 'people' in filters.values()

        if script:
            onload = "(function(obj){$$.convs.load(obj);})(this);"
            if fromFetchMore:
                yield renderScriptBlock(request, "search.mako", "results",
                                        landing, "#next-load-wrapper", "replace",
                                        True, handlers={"onload": onload}, **args)
            else:
                yield renderScriptBlock(request, "search.mako", "results",
                                        landing, "#search-results", "set", True,
                                        handlers={"onload": onload}, **args)
            if 'people' not in filters.values() and people:
              yield renderScriptBlock(request, "search.mako", "_displayUsersMini",
                                      landing, "#people-block", "set", True, **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "search.mako", **args)


    @profile
    @dump_args
    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self.search(request)
        return self._epilogue(request, d)

    def render_POST(self, request):
        return resource.NoResource("Page not found")

solr = Solr()
