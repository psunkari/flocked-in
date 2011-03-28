
import uuid

from telephus.cassandra import ttypes
from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from social             import Db, utils, _, __
from social.template    import render, renderDef, renderScriptBlock
from social.isocial     import IAuthInfo


@defer.inlineCallbacks
def ensureTag(request, tagName):
    authInfo = request.getSession(IAuthInfo)
    myId = authInfo.username
    myOrgId = authInfo.organization
    consistency = ttypes.ConsistencyLevel

    try:
        c = yield Db.get(myOrgId, "orgTagsByName",
                         tagName, consistency=consistency.QUORUM)
        tagId = c.column.value
        c = yield Db.get_slice(myOrgId, "orgTags", super_column=tagId,
                               consistency=consistency.QUORUM)
        tag = utils.columnsToDict(c)
    except ttypes.NotFoundException:
        tagId = utils.getUniqueKey()
        tag = {"title": tagName}
        yield Db.batch_insert(myOrgId, "orgTags",
                              {tagId: tag}, consistency=consistency.QUORUM)
        yield Db.insert(myOrgId, "orgTagsByName", tagId,
                        tagName, consistency=consistency.QUORUM)

    defer.returnValue((tagId, tag))

# TODO: Implement a resource to list all conversations with a given tag.
