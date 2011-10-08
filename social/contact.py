
from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, config, utils
from social.base            import BaseResource
from social.logging         import log

class ContactResource(BaseResource):
    isLeaf = True
    requireAuth = False

    _subjects = ["I have a question",
                 "I found a bug",
                 "I have a feature suggestion",
                 "I would like to introduce flocked-in at work...",
                 "I'm looking for a partnership..."]


    @defer.inlineCallbacks
    def _send(self, request):
        name = utils.getRequestArg(request, "name") or None
        email = utils.getRequestArg(request, "email") or None
        subject = utils.getRequestArg(request, "subject") or None
        message = utils.getRequestArg(request, "message") or None

        if not name or not email or not subject or not message:
            raise errors.MissingParams("Please fill-in all the fields")

        subject = "[flocked-in contact] %s" % self._subjects[int(subject)]
        toAddr = config.get('General', 'ContactId')
        yield utils.sendmail(toAddr, subject, message, fromAddr=email, fromName=name)
        request.redirect('/about/contact.html')


    def render_POST(self, request):
        d = None
        if len(request.postpath) == 0:
            d = self._send(request)

        return self._epilogue(request, d)
