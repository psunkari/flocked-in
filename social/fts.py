import time
import re
from base64                     import urlsafe_b64decode
from lxml                       import etree
from lxml.builder               import ElementMaker
from zope.interface             import implements
from urllib                     import quote, unquote
from markdown                   import markdown

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
#In devel environ set SOLR-URL in devel.cfg to http://localhost:8983/solr
DEBUG = False


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


class JsonBodyReceiver(protocol.Protocol):
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


class Solr(object):
    def __init__(self):
        self.url = URL
        self._headers = {}
        self.elementMaker = ElementMaker()

    def _request(self, method, url, headers=None, producer=None):
        if self.url:
            allHeaders = self._headers
            if headers:
                allHeaders.update(headers)
            agent = client.Agent(reactor)
            return agent.request(method, url, Headers(allHeaders), producer)
        else:
            return defer.succeed(None)


    def updatePeopleIndex(self, myId, me, orgId):
        def toUnicodeOrText(text):
            if isinstance(text, str):
                return text.decode('utf8', 'replace')
            elif isinstance(text, unicode):
                return text
            else:
                return str(text)
        mailId = me['basic']['emailId'].split('@')[0]

        fields = [self.elementMaker.field(str(myId), {"name":"id"}),
                  self.elementMaker.field(str(orgId), {"name":"orgId"}),
                  self.elementMaker.field('people', {"name":"itemType"}),
                  self.elementMaker.field(mailId, {'name':'mail'}) ]
        for field in ['name', 'lastname', 'firstname', 'jobTitle']:
            if field in me['basic']:
                fields.append(self.elementMaker.field(toUnicodeOrText(me['basic'][field]), {'name': field}))
        for field in ['mail', 'phone', 'im']:
            if field in me.get('contact', {}):
                fields.append(self.elementMaker.field(toUnicodeOrText(me['contact'][field]), {'name': field}))
        for field in ['email', 'phone', 'im', 'hometown', 'currentCity']:
            if field in me.get('personal', {}):
                fields.append(self.elementMaker.field(toUnicodeOrText(me['personal'][field]), {'name': field}))
        for school in me.get('schools', {}):
            value = "%s:%s" %(school, me['schools'][school])
            fields.append(self.elementMaker.field(toUnicodeOrText(value), {'name': "schools"}))
        for employer in me.get('companies', {}):
            value = "%s:%s" %(employer, me['companies'][employer])
            fields.append(self.elementMaker.field(toUnicodeOrText(value), {'name': "companies"}))

        skills = ','.join(me.get('expertise', {}).keys())
        interests = ','.join(me.get('interests', {}).keys())
        languages = ','.join(me.get('languages', {}).keys())
        if skills:
            fields.append(self.elementMaker.field(toUnicodeOrText(skills), {'name': 'expertise'}))
        if interests:
            fields.append(self.elementMaker.field(toUnicodeOrText(interests), {'name': 'interests'}))
        if languages:
            fields.append(self.elementMaker.field(toUnicodeOrText(languages), {'name': 'languages'}))
        fields.append(self.elementMaker.field(str(int(time.time())), {'name': 'timestamp'}))
        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        url = URL +  "/update?commit=true"
        return self._request("POST", url, {}, XMLBodyProducer(root))


    def updateIndex(self, itemId, item, orgId, attachments={}):
        fields = [self.elementMaker.field(str(itemId), {"name":"id"}),
                  self.elementMaker.field(str(orgId), {"name":"orgId"}),]
        itemType = item["meta"].get("type", "status")
        defaultIndex = [("meta", "comment"), ("meta", "parent")]
        richText = item['meta'].get('richText', 'False') == 'True'
        indices = defaultIndex
        if itemType in plugins and \
            getattr(plugins[itemType], "indexFields", defaultIndex):
            indices = getattr(plugins[itemType], "indexFields", defaultIndex)
        elif itemType == "message":
            indices = [('meta', 'subject'), ('meta', 'body'), ('meta', 'parent')]

        for key in indices:
            sfk, columnName = key
            value = item[sfk].get(columnName, None)
            if columnName == 'comment' and richText:
                value = utils.richTextToText(value)
            if value:
                if isinstance(value, str):
                    value = value.decode('utf-8', 'replace')
                elif not isinstance(value, unicode):
                    value = str(value)
                fields.append(self.elementMaker.field(value,
                               {"name":columnName}))
        file_info = []
        for attachmentId in attachments:
            timeuuid, fid, name, size, ftype  = attachments[attachmentId]
            file_info.append("%s:%s:%s:%s:%s"%(urlsafe_b64decode(name), fid, utils.encodeKey(timeuuid), size, ftype))
        if file_info:
            fields.append(self.elementMaker.field(",".join(file_info), {"name":"filename"}))
        if "timestamp" in item.get("meta", {}):
            fields.append(self.elementMaker.field(item['meta']['timestamp'], {"name":"timestamp"}))
        fields.append(self.elementMaker.field(itemType, {"name":"itemType"}))
        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        url = URL +  "/update?commit=true"
        return self._request("POST", url, {}, XMLBodyProducer(root))


    def deleteIndex(self, itemId):
        root = self.elementMaker.delete(self.elementMaker.id(str(itemId)))
        url = URL +  "/update?commit=true"
        return self._request("POST", url, {}, XMLBodyProducer(root))

    def search(self, term, orgId, count, start=0, filters=None):
        def callback(response):
            finished = defer.Deferred()
            response.deliverBody(JsonBodyReceiver(finished))
            return finished
        term = quote(term)
        url = URL + "/select?q=%s&start=%s&rows=%s&fq=orgId:%s&sort=%s&hl=true&hl.fl=comment" % (term, start, count, orgId, quote('timestamp desc'))
        if filters:
            for x in filters:
                url += '&fq=%s:%s' %(x, filters[x])
        d = self._request("GET", url)
        d.addCallback(callback)
        return d


class FTSResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def search(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']
        filter_map = {'people':'itemType'}

        term = utils.getRequestArg(request, "q")
        start = utils.getRequestArg(request, "start") or 0
        filters = utils.getRequestArg(request, 'filter', multiValued=True) or []
        filters = dict([(filter_map[x], x) for x in filters if x in filter_map])
        args["term"] = term
        prevPageStart = ''
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

        if start - SEARCH_RESULTS_PER_PAGE >= 0:
            prevPageStart = start - SEARCH_RESULTS_PER_PAGE

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
                                        landing, "#user-feed", "set", True,
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
