import embedly
import urllib
from lxml               import etree

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer, threads
from twisted.plugin     import IPlugin
from twisted.web        import client

from social.template    import renderScriptBlock, getBlock
from social.isocial     import IItemType, IAuthInfo
from social             import db, utils, errors, _, config
from social.logging     import profile, dump_args

_encode = lambda x: type(x) == unicode and x.encode('utf8', 'replace') or x
embedlyKey = config.get('Embedly', 'Key')
embedlyClient = None
if embedlyKey:
    embedlyClient = embedly.client.Embedly(key=embedlyKey)
    embedlyClient.get_services()


class Links(object):
    implements(IPlugin, IItemType)
    itemType = "link"
    position = 3
    hasIndex = True
    indexFields = [('meta', 'summary'), ('meta', 'comment'),
                   ('meta', 'title'), ('meta', 'parent')]


    @defer.inlineCallbacks
    def renderShareBlock(self, request, isAjax):
        templateFile = "feed.mako"
        renderDef = "share_link"
        yield renderScriptBlock(request, templateFile, renderDef,
                                not isAjax, "#sharebar", "set", True,
                                attrs={"publisherName": "link"},
                                handlers={"onload": "(function(obj){$$.publisher.load(obj)})(this);"})
    def rootHTML(self, convId, isQuoted, args):
        if "convId" in args:
            return getBlock("item.mako", "render_link", **args)
        else:
            return getBlock("item.mako", "render_link", args=[convId, isQuoted], **args)


    def fetchData(self, args, convId=None):
        return defer.succeed(set())


    @profile
    @defer.inlineCallbacks
    @dump_args
    def create(self, request):
        target = utils.getRequestArg(request, "target")
        comment = utils.getRequestArg(request, "comment")
        url = utils.getRequestArg(request, "url", sanitize=False)
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        if not url:
            raise errors.MissingParams([_('URL to be shared')])

        if len(url.split()) >1:
            match = utils._urlRegEx.search(url)
            if match:
                url = match.group()
            else:
                raise errors.InvalidRequest(_("Invalid URL '%s'")%(url))

        if len(url.split("://")) == 1:
            url = "http://" + url

        summary, title, image, embed = yield self._summary(url)
        summary = _encode(summary)
        title = _encode(title)

        convId = utils.getUniqueKey()
        item, attachments = yield utils.createNewItem(request, self.itemType)
        meta = {"comment": comment}
        if target:
            meta["target"] = target
        if summary:
            meta["summary"] = summary
        if title:
            meta["title"] = title
        if image:
            meta['imgSrc'] = image
        if embed:
            embedType = embed.get("type")
            embedSrc = embed.get("url") if embedType == "photo" else embed.get("html")
            embedWidth = embed.get("width")
            embedHeight = embed.get("height")
            if embedHeight and embedWidth and embedSrc:
                meta["embedType"] = embedType
                meta["embedSrc"] = embedSrc
                meta["embedHeight"] = str(embedHeight)
                meta["embedWidth"] = str(embedWidth)

        meta["url"] = url
        item["meta"].update(meta)

        yield db.batch_insert(convId, "items", item)

        for attachmentId in attachments:
            timeuuid, fid, name, size, ftype  = attachments[attachmentId]
            val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
            yield db.insert(convId, "item_files", val, timeuuid, attachmentId)

        from social import fts
        fts.solr.updateIndex(convId, item, myOrgId, attachments)
        defer.returnValue((convId, item))

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield db.get_slice(itemId, "entities")

    def getResource(self, isAjax):
        return None

    @defer.inlineCallbacks
    def _summary(self, url):
        parser = etree.HTMLParser()
        summary = None
        title = None
        image = None
        ogTitle = None
        ogSummary = None
        ogImage = None
        embed = None
        try:
            # First check if embedly supports it.
            if embedlyClient and embedlyClient._regex.match(url):
                kwargs = {'maxwidth': 400, 'autoplay': 1}
                obj = yield threads.deferToThread(embedlyClient.oembed, url, **kwargs)
                if obj.get('error') != True:
                    image = obj.get('thumbnail_url')
                    title = obj.get("title")
                    summary = obj.get("description")
                    embedType = obj.get("type")
                    if embedType in ["photo", "video", "audio"]:
                        defer.returnValue((summary, title, image, obj))
                    else:
                        defer.returnValue((summary, title, image, None))

            #XXX: client.getPage starts and stops HTTPClientFactory everytime
            #     find a way to avoid this
            d = client.getPage(url)
            data = yield d
            domain = url.split('/', 3)[2]
            parser.feed(data)
            tree = parser.close()
            titleElement = tree.xpath("head/title")
            if titleElement:
                title = titleElement[0].text
            meta = tree.xpath("//meta")
            for element in meta:
                if element.attrib.get('property', '') == 'og:title':
                    ogTitle = element.attrib.get('content', '')
                    ogTitle = ogTitle.encode('utf-8')
                if element.attrib.get('property', '') == 'og:description':
                    ogSummary = element.attrib.get('content', '')
                    ogSummary = ogSummary.encode('utf-8')

                if element.attrib.get('property', '') == 'og:image':
                    ogImage = element.attrib.get('content', '')

                if element.attrib.get('name', '') in ['description', 'Description']:
                    summary = element.attrib.get('content', '')
                    summary = summary.encode('utf-8')

            if ((ogSummary or summary) and (ogTitle or title) and (ogImage or image)):
                defer.returnValue((ogSummary or summary, ogTitle or title,  ogImage or image, embed ))
            if not (ogSummary or summary):
                for element in tree.xpath("body//p"):
                    if element.text:
                        summary = element.text
                        break
            if not (ogImage or image):
                for element in tree.xpath("body//img"):
                    if 'src' in element.attrib \
                      and element.attrib['src'].startswith('http://') \
                      and domain in element.attrib['src']:

                        image = element.attrib['src']
                        break
            defer.returnValue((ogSummary or summary, ogTitle or title, ogImage or image, embed))
        except Exception as e:
            log.msg(e)
            defer.returnValue((ogSummary or summary, ogTitle or title, ogImage or image, embed))


links = Links()
