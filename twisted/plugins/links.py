
import time
import uuid
import urllib2
from lxml               import etree
import re

from zope.interface     import implements
from twisted.python     import log
from twisted.internet   import defer
from twisted.plugin     import IPlugin

from social.template    import renderScriptBlock, render, getBlock
from social.isocial     import IItemType
from social             import Db, base, utils, errors
from social.logging     import profile, dump_args


class Links(object):
    implements(IPlugin, IItemType)
    itemType = "link"
    position = 3
    hasIndex = True
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
        url = utils.getRequestArg(request, "url")

        if not url:
            raise errors.MissingParams()

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url

        summary, title, image =  self._summary(url)

        convId = utils.getUniqueKey()
        item = utils.createNewItem(request, self.itemType)
        meta = {"comment": comment}
        if target:
            meta["target"] = target
        if summary:
            meta["summary"] = summary
        if title:
            meta["title"] = title
        if image:
            meta['imgSrc'] = image
        meta["url"] = url

        item["meta"].update(meta)

        yield Db.batch_insert(convId, "items", item)
        defer.returnValue((convId, item))

    @defer.inlineCallbacks
    def delete(self, itemId):
        yield Db.get_slice(itemId, "entities")

    def getResource(self, isAjax):
        return None


    def _summary(self, url):

        parser = etree.HTMLParser()
        summary = None
        title = None
        ogTitle = None
        ogSummary = None
        ogImage = None
        image = None
        try:
            foo = urllib2.urlopen(url)
            domain = url.split('/', 3)[2]
            data = foo.read()
            parser.feed(data)
            tree = parser.close()
            titleElement = tree.xpath("head/title")
            if titleElement:
                title = titleElement[0].text
            meta = tree.xpath("//meta")
            for element in meta:
                if element.attrib.get('property','') == 'og:title':
                    ogTitle = element.attrib.get('content', '')
                    ogTitle = ogTitle.encode('utf-8')
                if element.attrib.get('property', '') == 'og:description':
                    ogSummary = element.attrib.get('content', '')
                    ogSummary = ogSummary.encode('utf-8')

                if element.attrib.get('property', '') == 'og:image':
                    ogImage = element.attrib.get('content', '')

                if element.attrib.get('name', '') in ['description']:
                    summary = element.attrib.get('content', '')
                    summary = summary.encode('utf-8')

            if ((ogSummary or summary) and (ogTitle or title) and (ogImage)):
                return (ogSummary or summary, ogTitle or title,  ogImage)
            if not ogSummary or summary:
                for element in tree.xpath("body//p"):
                    if element.text:
                        summary = element.text
                        break
            if not ogImage:
                for element in tree.xpath("body//img"):
                    if 'src' in element.attrib \
                        and element.attrib['src'].startswith('http://') \
                        and domain in element.attrib['src']:
                            image = element.attrib['src']
                            break
            return (ogSummary or summary, ogTitle or title,  ogImage or image)
        except Exception as e:
            log.msg(e)
            return(ogSummary or summary, ogTitle or title,  ogImage or image)


links = Links()
