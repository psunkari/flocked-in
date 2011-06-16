from lxml                       import etree
from lxml.builder               import ElementMaker
from zope.interface             import implements

from twisted.web                import server, client
from twisted.web.iweb           import IBodyProducer
from twisted.internet           import protocol,reactor, defer
from twisted.python             import log
from twisted.web.http           import PotentialDataLoss
from twisted.web.http_headers   import Headers

from social                     import base, db, utils, config
from social                     import errors, plugins, _
from social.feed                import FeedResource
from social.template            import render, renderScriptBlock
from social.logging             import dump_args, profile


URL = config.get('SOLR', 'HOST')
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

    def updateIndex(self, itemId, item):
        fields = [self.elementMaker.field(str(itemId), {"name":"id"})]
        itemType = item["meta"].get("type", "status")
        defaultIndex = [("meta", "comment"), ("meta", "parent")]
        if itemType in plugins and \
            getattr(plugins[itemType], "indexFields", defaultIndex):
            for key in getattr(plugins[itemType], "indexFields", defaultIndex):
                sfk, columnName = key
                value = item[sfk].get(columnName, None)
                if value:
                    fields.append(self.elementMaker.field(str(value), {"name":columnName}))


        root = self.elementMaker.add(self.elementMaker.doc(*fields))
        url = URL +  "/update?commit=true"

        return self._request("POST", url, {}, XMLBodyProducer(root))

    def deleteIndex(self, itemId, item):
        pass

    def search(self, term):
        def callback(response):
            finished = defer.Deferred()
            response.deliverBody(JsonBodyReceiver(finished))
            return finished

        url = URL + "/select?q=%s"%(term)
        d = self._request("GET", url)
        d.addCallback(callback)
        return d


class FTSResource(base.BaseResource):
    isLeaf=True

    @profile
    @defer.inlineCallbacks
    @dump_args
    def search(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        args["heading"] = _("Search Results")

        term = utils.getRequestArg(request, "searchbox")
        if not term:
            errors.MissingParams()

        if script and landing:
            yield render(request, "feed.mako", **args)

        if script and appchange:
            yield renderScriptBlock(request, "feed.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        res = yield solr.search(term)
        data = res.data
        convs = []
        for item in data.get('response', {}).get('docs', []):
            parent = item.get('parent', None)
            if parent:
                if parent not in convs:
                    convs.append(parent)
            else:
                convs.append(item.get('id'))

        if convs:
            feedResource = FeedResource()
            feedItems = yield feedResource._getFeedItems(request, itemIds=convs)
            args.update(feedItems)
        else:
            args["conversations"] = convs

        if script:
            yield renderScriptBlock(request, "feed.mako", "feed", landing,
                                    "#user-feed", "set", **args)

        if script and landing:
            request.write("</body></html>")

        if not script:
            yield render(request, "feed.mako", **args)

    @profile
    @dump_args
    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            d = self.search(request)
        return self._epilogue(request, d)

    @profile
    @dump_args
    def render_GET(self, request):
        request.redirect("/feed")
        return ""

solr = Solr()
