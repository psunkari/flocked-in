
from twisted.internet       import defer
from twisted.web            import resource, server, http, static

from social                 import _, __, config, utils, errors
from social.base            import BaseResource
from social.logging         import log


try:
    checkTemplateUpdates = config.get('Devel', 'CheckTemplateUpdates')
except:
    checkTemplateUpdates = False


class AboutResource(BaseResource):
    isLeaf = True
    requireAuth = False

    _available = ('why', 'tour', 'features', 'contact', 'message-sent')
    _cache = {}
    _subjects = ["",    # The values in the form start at 1
                 "I have a question",
                 "I found a bug",
                 "I have a feature request",
                 "I would like to introduce flocked-in at work...",
                 "I'm looking for a partnership...",
                 "I would like to join Flocked-in team"]

    def pages(self):
        return [('POST', '^/contact$', self.send),
                ('GET',  '^/(?P<page>[^/]*).html$', self.page)]

    @defer.inlineCallbacks
    def send(self, request):
        name = utils.getRequestArg(request, "name") or None
        email = utils.getRequestArg(request, "email") or None
        subject = utils.getRequestArg(request, "subject") or None
        message = utils.getRequestArg(request, "message") or None

        if not name or not email or not subject or not message:
            raise errors.MissingParams(["Please fill-in all the fields"])

        if not 0 < int(subject) < len(self._subjects):
            return

        subject = "[flocked-in contact] %s" % self._subjects[int(subject)]
        toAddr = config.get('General', 'ContactId')
        yield utils.sendmail(toAddr, subject, message, fromAddr=email, fromName=name)

        if not self.thanksPage:
            self.thanksPage = static.File("public/thanks-for-contacting.html")
        if self.thanksPage:
            yield self.thanksPage.render_GET(request)

    def page(self, request, page):
        if page not in self._available:
            raise errors.NotFoundError()

        if page not in self._cache:
            template = t.getBlock('static/%s.mako' % page)
            if not checkTemplateUpdates:
                self._cache[page] = template

        request.write(self._cache[page])

    def render_POST(self, request):
        d = None
        if len(request.postpath) == 1 and request.postpath[0] == "contact":
            d = self._send(request)
        return self._epilogue(request, d)

