from lxml                       import etree
from lxml.builder               import ElementMaker
from zope.interface             import implements

from twisted.web                import client
from twisted.web.iweb           import IBodyProducer
from twisted.internet           import protocol, reactor, defer
from twisted.python             import log
from twisted.web.http           import PotentialDataLoss
from twisted.web.http_headers   import Headers

from social                     import base, utils, config, feed
from social                     import errors, plugins, _
from social.constants           import SEARCH_RESULTS_PER_PAGE
from social.template            import render, renderScriptBlock
from social.logging             import dump_args, profile


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
        allHeaders = self._headers
        if headers:
            allHeaders.update(headers)
        agent = client.Agent(reactor)
        d = agent.request(method, url, Headers(allHeaders), producer)
        return d

    def updateIndex(self, itemId, item, orgId):
        fields = [self.elementMaker.field(str(itemId), {"name":"id"}),
                  self.elementMaker.field(str(orgId), {"name":"orgId"}),]
        itemType = item["meta"].get("type", "status")
        defaultIndex = [("meta", "comment"), ("meta", "parent")]
        if itemType in plugins and \
            getattr(plugins[itemType], "indexFields", defaultIndex):
            for key in getattr(plugins[itemType], "indexFields", defaultIndex):
                sfk, columnName = key
                value = item[sfk].get(columnName, None)
                if value:
                    if type(value) in [str, unicode]:
                        value = value.decode('utf8', 'replace')
                        fields.append(self.elementMaker.field((value),
                                  {"name":columnName}))
                    else:
                        fields.append(self.elementMaker.field(str(value),
                                  {"name":columnName}))


        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        url = URL +  "/update?commit=true"
        return self._request("POST", url, {}, XMLBodyProducer(root))


    def deleteIndex(self, itemId):
        root = self.elementMaker.delete(self.elementMaker.id(str(itemId)))
        url = URL +  "/update?commit=true"
        return self._request("POST", url, {}, XMLBodyProducer(root))

    def search(self, term, orgId, start=0):
        def callback(response):
            finished = defer.Deferred()
            response.deliverBody(JsonBodyReceiver(finished))
            return finished
        rows = SEARCH_RESULTS_PER_PAGE
        url = URL + "/select?q=%s&start=%s&rows=%s&fq=orgId:%s" % (term, start, rows, orgId)
        d = self._request("GET", url)
        d.addCallback(callback)
        return d


class FTSResource(base.BaseResource):
    isLeaf = True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def search(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        term = utils.getRequestArg(request, "q")
        start = utils.getRequestArg(request, "start") or 0
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

        res = yield solr.search(term, args['orgKey'], start)
        data = res.data
        convs = []
        numMatched = data.get('response', {}).get('numFound', 0)
        for item in data.get('response', {}).get('docs', []):
            parent = item.get('parent', None)
            if parent:
                if parent not in convs:
                    convs.append(parent)
            else:
                convs.append(item.get('id'))
        if convs:
            feedItems = yield feed.getFeedItems(request, convIds=convs, count=len(convs))
            args.update(feedItems)
        else:
            args["conversations"] = convs

        if start + SEARCH_RESULTS_PER_PAGE < numMatched:
            nextPageStart = start + SEARCH_RESULTS_PER_PAGE
        if start - SEARCH_RESULTS_PER_PAGE >= 0:
            prevPageStart = start - SEARCH_RESULTS_PER_PAGE

        args["nextPageStart"] = nextPageStart
        args["prevPageStart"] = prevPageStart

        if script:
            yield renderScriptBlock(request, "search.mako", "results", landing,
                                    "#user-feed", "set", **args)
            yield renderScriptBlock(request, "search.mako", "paging", landing,
                                    "#search-paging", "set", **args)

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
