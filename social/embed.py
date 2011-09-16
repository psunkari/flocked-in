
from telephus.cassandra     import ttypes
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils
from social.base            import BaseResource
from social.isocial         import IAuthInfo
from social.logging         import log


class EmbedResource(BaseResource):
    isLeaf = True
    _template = """
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
                <html><body style='margin:0;padding:0;'>%s</body></html>
                """

    @defer.inlineCallbacks
    def _link(self, request):
        itemId, item = yield utils.getValidItemId(request, 'id', 'link')
        meta = item.get('meta', {})
        embedType = meta.get('embedType', '')
        embedSrc = meta.get('embedSrc', '')
        if embedSrc:
            if embedType == "photo":
                src = '<img src="%s"></img>' % embedSrc
            elif embedType in ["video", "audio"]:
                src = item.get('meta', {}).get('embedSrc', '')
            if src:
                request.write(self._template % src)
        request.finish()

    def render_GET(self, request):
        if len(request.postpath) == 0:
            return resource.ErrorPage(404, http.RESPONSES[404],
                                      "Resource not found")
        path = request.postpath[0]
        d = None

        if path == "link":
            d = self._link(request)
        return self._epilogue(request, d)
