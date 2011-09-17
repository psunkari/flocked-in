
import time
from email.utils            import formatdate

from twisted.internet       import defer
from twisted.web            import resource, server, http

from social                 import _, __, db, utils
from social.logging         import profile, dump_args, log

class AvatarResource(resource.Resource):
    isLeaf = True

    @profile
    @dump_args
    def render_GET(self, request):
        if len(request.postpath) != 1:
            return resource.ErrorPage(404, http.RESPONSES[401],
                                      "Resource not found")

        size, itemId = request.postpath[0].split("_", 1)
        size = {"s": "small", "m": "medium", "l": "large"}[size]
        itemId = itemId.split(".")[0]

        d = db.get_slice(itemId, "items",
                         [size, "format"], super_column="avatar")
        def callback(cols):
            avatarInfo = utils.columnsToDict(cols)
            format = avatarInfo["format"]\
                     if avatarInfo.has_key("format") else "jpg"
            data = avatarInfo[size]
            expires = formatdate(time.time() + 31536000)

            request.setHeader('Content-Type', 'image/%s' % format)
            request.setHeader('Content-Length', len(data))
            request.setHeader('Cache-control', 'public')
            request.setHeader('Expires', expires)
            request.write(data)
            request.finish()

        def errback(err):
            log.error("Avatar fetching: ", err)
            request.finish()

        d.addCallback(callback)
        d.addErrback(errback)

        return server.NOT_DONE_YET
