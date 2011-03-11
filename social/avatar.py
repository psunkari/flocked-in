
from twisted.internet       import defer
from twisted.python         import log
from twisted.web            import resource, server, http

from social import _, __, Db, utils

class AvatarResource(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        if len(request.postpath) != 1:
            return resource.ErrorPage(404, http.RESPONSES[401],
                                      "Resource not found")

        size, itemId = request.postpath[0].split("_", 2)
        size = {"s": "small", "m": "medium", "l": "large"}[size]
        itemId = itemId.split(".")[0]

        d = Db.get_slice(itemId, "items",
                         [size, "format"], super_column="avatar")
        def callback(cols):
            avatarInfo = utils.columnsToDict(cols)
            format = avatarInfo["format"]\
                     if avatarInfo.has_key("format") else "jpg"
            data = avatarInfo[size]

            request.setHeader('Content-Type', 'image/%s' % format)
            request.setHeader('Content-Length', len(data))
            request.write(data)
            request.finish()

        def errback(err):
            log.msg("Avatar fetching: ", err)
            request.finish()

        d.addCallback(callback)
        d.addErrback(errback)

        return server.NOT_DONE_YET
