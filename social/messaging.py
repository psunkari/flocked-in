import uuid
import re
import time
import mimetypes
from base64             import urlsafe_b64decode
from email.header       import Header

import boto
from telephus.cassandra import ttypes
from txaws.credentials  import AWSCredentials
from txaws.s3           import client as s3Client
from boto.s3.connection import S3Connection
from boto.s3.connection import VHostCallingFormat, SubdomainCallingFormat

from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _, search
from social             import notifications, template as t
from social             import constants
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.logging     import profile, dump_args, log


class MessagingResource(base.BaseResource):
    isLeaf = True
    _templates = ['message.mako']
    _folders = {'inbox': 'mAllConversations',
                'archive': 'mArchivedConversations',
                'trash': 'mDeletedConversations',
                'unread': 'mUnreadConversations'}

    def _formatAttachMeta(self, attachments):
        attach_meta = {}
        for attachmentId in attachments:
            fileId, name, size, ftype = attachments[attachmentId]
            val = "%s:%s:%s" % (name, size, ftype)
            attach_meta[attachmentId] = val

        return attach_meta

    def _indexMessage(self, convId, messageId, myOrgId, meta, attachments, body):
        meta['type'] = "message"
        meta['body'] = body
        meta['parent'] = convId
        meta['timestamp'] = meta['date_epoch']
        meta = {"meta": meta}
        search.solr.updateMessageIndex(messageId, meta, myOrgId)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _handleAttachments(self, request):
        """Commit the files that were uploaded to S3 with the conversation.
        Returns a dictionary mapping of each file and its meta info like
        name, mimeType, version id.

        Keyword Arguments:
        tmpFileIds: A list of file ids on the S3 system that are to be associated
            with this conversation.

        """
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        tmpFileIds = utils.getRequestArg(request, 'fId', False, True)
        attachments = {}
        if tmpFileIds:
            attachments = yield utils._upload_files(myId, tmpFileIds)
        defer.returnValue((attachments))

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _getFileInfo(self, request):
        """Fetch the meta info on a file that is being requested to be
        downloaded. Returns the meta info of the file in question.

        Keyword Arguments:
        itemId: id of the conversation on which this file is attached.
        attachmentId: id of the file on the amazon S3 that is to be served.
        version: version of the file on the amazon S3 that the user is
            requesting.

        """
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        itemId = utils.getRequestArg(request, "id", sanitize=False)
        attachmentId = utils.getRequestArg(request, "fid", sanitize=False)
        version = utils.getRequestArg(request, "ver", sanitize=False) or ''
        columns = ["meta", "attachments", "participants"]

        if not (itemId and attachmentId):
            raise errors.MissingParams([])

        item = yield db.get_slice(itemId, "mConversations", columns)
        item = utils.supercolumnsToDict(item)
        if not item:
            raise errors.InvalidMessage(itemId)
        if myId not in item.get('participants', {}):
            raise errors.MessageAccessDenied(itemId)

        # Check if the attachmentId belong to item
        if attachmentId not in item['attachments'].keys():
            raise errors.InvalidAttachment(itemId, attachmentId, version)

        fileId, filetype, name = None, 'text/plain', 'file'
        if version:
            version = utils.decodeKey(version)
            try:
                cols = yield db.get(attachmentId, "attachmentVersions", version)
            except ttypes.NotFoundException:
                raise errors.InvalidAttachment(itemId, attachmentId, version)
            except ttypes.InvalidRequestException:
                raise errors.InvalidAttachment(itemId, attachmentId, version)
            cols = utils.columnsToDict([cols])
        else:
            cols = yield db.get_slice(attachmentId, "attachmentVersions",
                                      count=1, reverse=True)
            cols = utils.columnsToDict(cols)
            version = cols.keys()[0]

        fileId, name, size, filetype = cols[version].split(':')

        files = yield db.get_slice(fileId, "files", ["meta"])
        files = utils.supercolumnsToDict(files)

        url = files['meta']['uri']
        owner = files["meta"]["owner"]
        defer.returnValue([owner, url, filetype, size, name])

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderFile(self, request):
        """Allow the user to download a file attached to a conversation.
        Redirects the user to the donwload location on S3.

        Keyword arguments:
        filename: The name of the file.
        myId: userId of the person who uploaded the file.
        myOrgId: orgId of the currently logged in user.
        fileType: mimeType of the file as detected during uploading.
        url: filename of the file object in the Amazon S3 system.

        """
        fileInfo = yield self._getFileInfo(request)
        owner, url, fileType, size, name = fileInfo
        authinfo = request.getSession(IAuthInfo)
        myOrgId = authinfo.organization

        filename = urlsafe_b64decode(name)
        try:
            filename.decode('ascii')
        except UnicodeDecodeError:
            filename = filename.decode('utf-8').encode('utf-8')
            filename = str(Header(filename, "UTF-8")).encode('string_escape')
        else:
            filename = filename.encode('string_escape')

        headers = {'response-content-type': fileType,
                 'response-content-disposition': 'attachment;filename=\"%s\"' % filename,
                 'response-expires': '0'}

        SKey = config.get('CloudFiles', 'SecretKey')
        AKey = config.get('CloudFiles', 'AccessKey')
        domain = config.get('CloudFiles', 'Domain')
        bucket = config.get('CloudFiles', 'Bucket')
        if domain == "":
            calling_format = SubdomainCallingFormat()
            domain = "s3.amazonaws.com"
        else:
            calling_format = VHostCallingFormat()
        conn = S3Connection(AKey, SKey, host=domain,
                            calling_format=calling_format)

        Location = conn.generate_url(600, 'GET', bucket,
                                     '%s/%s/%s' % (myOrgId, owner, url),
                                     response_headers=headers)

        request.setResponseCode(307)
        request.setHeader('Location', Location)

    def _parseComposerArgs(self, request):
        """Parse the request object for common conversation related fields.
        Return the tuple of (recipients, body, subject, parent)

        Keyword Arguments:
        recipients: A list of valid user ids who are party to this conversation.
        subject: The subject of this conversation.
        body: The body or actual message of this request.
        parent: Optional, the id of the conversation to which request was acted
            upon. This is optional if it is a new conversation else a valid id
            in mConversations.

        """
        #Since we will deal with composer related forms. Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        if body:
            body = body.decode('utf-8').encode('utf-8', "replace")
        parent = utils.getRequestArg(request, "parent")
        subject = utils.getRequestArg(request, "subject") or ''
        if subject:
            subject.decode('utf-8').encode('utf-8', "replace")

        recipients = utils.getRequestArg(request, "recipients", sanitize=False)
        if recipients:
            recipients = re.sub(',\s+', ',', recipients).split(",")
        else:
            #When using the new composer dialog, the widget returns the
            # selected tags in "recipient[id]" format
            arg_keys = request.args.keys()
            recipients = []
            for arg in arg_keys:
                if arg.startswith("recipient["):
                    rcpt = arg.replace("recipient[", "").replace("-a]", "")
                    if rcpt != "":
                        recipients.append(rcpt)

        return recipients, body, subject, parent

    def _fetchSnippet(self, body):
        #XXX:obviously we need a better regex than matching ":wrote"
        lines = body.split("\n")
        snippet = ""
        for line in lines:
            if not line.startswith(">") or not "wrote:" in line:
                snippet = line[:120]
                break
            else:
                continue
        return snippet

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _deliverMessage(self, convId, recipients, timeUUID, owner):
        """To each participant in a conversation, add the conversation
        to the list of unread conversations.

        CF Changes:
        mConversations
        mConvFolders
        messages
        mAllConversations
        mDeletedConversations
        mArchivedConversations
        latest

        """
        convFolderMap = {}
        userFolderMap = {}
        toNotify = {}
        toRemove = {'latest': []}
        conv = yield db.get_slice(convId, "mConversations", ['meta'])
        conv = utils.supercolumnsToDict(conv)

        oldTimeUUID = conv['meta']['uuid']
        unread = "u:%s" % (convId)
        read = "r:%s" % (convId)

        cols = yield db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in recipients:
            deliverToInbox = True
            # for a new message, mConvFolders will be empty
            # so recipient may not necessarily be present in cols
            if recipient != owner:
                toNotify[recipient] = {'latest': {'messages': {timeUUID: convId}}}
            toRemove['latest'].append(recipient)

            for folder in cols.get(recipient, []):
                cf = self._folders[folder] if folder in self._folders else folder
                yield db.remove(recipient, cf, oldTimeUUID)
                if cf == 'mDeletedConversations':
                    #don't add to recipient's inbox if the conv is deleted.
                    deliverToInbox = False
                else:
                    yield db.remove(convId, 'mConvFolders', folder, recipient)
            if deliverToInbox:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mAllConversations':
                                                            {timeUUID: val}}
                userFolderMap[recipient] = {'mAllConversations': ''}
                if recipient != owner:
                    convFolderMap[recipient]['mUnreadConversations'] = \
                        {timeUUID: unread}
                    userFolderMap[recipient]['mUnreadConversations'] = ''

            else:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mDeletedConversations':
                                                            {timeUUID: val}}

        yield db.batch_mutate(convFolderMap)
        yield db.batch_insert(convId, "mConvFolders", userFolderMap)
        if toRemove['latest'] and oldTimeUUID != timeUUID:
            yield db.batch_remove(toRemove, names=[oldTimeUUID],
                                    supercolumn="messages")
        if toNotify:
            yield db.batch_mutate(toNotify)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _newMessage(self, ownerId, timeUUID, body, epoch):
        """Commit the meta information of a message. A message is a reply to a
        an existing conversation or the first message of a new conversation.

        CF Changes:
        messages

        """
        messageId = utils.getUniqueKey()
        meta = {"owner": ownerId,
                "timestamp": str(int(time.time())),
                'date_epoch': str(epoch),
                "body": body,
                "uuid": timeUUID}
        yield db.batch_insert(messageId, "messages", {'meta': meta})
        defer.returnValue(messageId)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _newConversation(self, ownerId, participants, meta, attachments):
        """Commit the meta information about a new conversation. Returns
        the conversation id of the newly created conversation.

        CF Changes:
        mConversations

        """
        participants = dict([(userId, '') for userId in participants])
        convId = utils.getUniqueKey()
        attach_meta = self._formatAttachMeta(attachments)
        yield db.batch_insert(convId, "mConversations", {"meta": meta,
                                                "participants": participants,
                                                "attachments": attach_meta})
        defer.returnValue(convId)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _reply(self, request):
        """Commit a new message in reply to an existing conversation. Creates
        a new message, uploads any attachments, updates the conversation meta
        info and finally renders the message for the user.

        Keyword Arguments:
        convId: conversation id to which this user is replying to.
        body: The content of the reply.

        CF Changes:
        mConversations
        mConvMessages
        attachmentVersions

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']

        convId = utils.getRequestArg(request, 'id')
        recipients, body, subject, convId = self._parseComposerArgs(request)
        epoch = int(time.time())

        if not convId:
            raise errors.MissingParams([])

        cols = yield db.get_slice(convId, "mConversations",
                                    ['meta', 'participants'])
        cols = utils.supercolumnsToDict(cols)
        subject = cols['meta'].get('subject', None)
        participants = cols.get('participants', {}).keys()
        if not cols:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet": snippet}

        attachments = yield self._handleAttachments(request)
        attach_meta = self._formatAttachMeta(attachments)

        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield db.batch_insert(convId, "mConversations",
                              {'meta': meta, 'attachments': attach_meta})

        # Currently, we don't support searching for private messages
        # self._indexMessage(convId, messageId, myOrgId, meta, attachments, body)

        #XXX:We currently only fetch the message we inserted. Later we may fetch
        # all messages delivered since we last rendered the conversation
        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv['participants'])
        mids = [messageId]
        messages = yield db.multiget_slice(mids, "messages", ["meta"])
        messages = utils.multiSuperColumnsToDict(messages)
        participants.update([messages[mid]['meta']['owner'] for mid in messages])

        people = base.EntitySet(participants)
        yield people.fetchData()

        value = myId
        data = {"entities": people}
        data["entities"].update({args['orgId']: args["org"]})
        data["orgId"] = args["orgId"]
        data["convId"] = convId
        data["message"] = body
        data["subject"] = subject
        data["_fromName"] = people[value].basic['name']

        users = participants - set([myId])
        if users:
            yield notifications.notify(users, ":MR", value, timeUUID, **data)

        args.update({"convId": convId})
        args.update({"people": people})
        args.update({"messageIds": mids})
        args.update({'messages': messages})
        if script:
            onload = """
                        $('.conversation-reply').attr('value', '');
                        $('#msgreply-attach-uploaded').empty();
                     """
            t.renderScriptBlock(request, "message.mako",
                                "conversation_messages", landing,
                                ".conversation-messages-wrapper", "append", True,
                                handlers={"onload": onload}, **args)

        #Update the right side bar with any attachments the user uploaded
        args.update({"conv": conv})
        people = base.EntitySet(set(conv['participants']))
        yield people.fetchData()

        args.update({"people": people})
        args.update({"conv": conv})
        args.update({"view": "message"})
        if script:
            onload = """
                     $('#conversation_add_member').autocomplete({
                           source: '/auto/users',
                           minLength: 2,
                           select: function( event, ui ) {
                               $('#conversation_recipients').attr('value', ui.item.uid);
                           }
                      });
                     """
            t.renderScriptBlock(request, "message.mako", "right",
                                landing, ".right-contents", "set", True,
                                handlers={"onload": onload}, **args)

        else:
            request.redirect('/messages')
            request.finish()

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _createConversation(self, request):
        """Create a new conversation including committing meta info about the
        conversation and the message.

        Keyword Arguments:
        recipients: A list of user ids who also receive this conversation.
        body: Text of the first message in this conversation.
        subject: Subject of the conversation.

        CF Changes:
        mConvMessages
        attachmentVersions

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgId']
        epoch = int(time.time())

        recipients, body, subject, parent = self._parseComposerArgs(request)
        filterType = utils.getRequestArg(request, "filterType") or None

        if not parent and not recipients:
            raise errors.MissingParams(['Recipients'])

        if not subject and not body:
            raise errors.MissingParams(['Both subject and message'])

        recipients = base.EntitySet(recipients)
        yield recipients.fetchData()
        recipients = set([userId for userId in recipients.keys() \
                            if not recipients[userId].isEmpty()])
        if not recipients:
            raise errors.MissingParams(['Recipients'])

        recipients.add(myId)
        participants = list(recipients)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet": snippet,
                'subject': subject, "owner": myId,
                "timestamp": str(int(time.time()))}
        attachments = yield self._handleAttachments(request)

        convId = yield self._newConversation(myId, participants, meta, attachments)
        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)

        self._indexMessage(convId, messageId, myOrgId, meta, attachments, body)

        #XXX: Is this a duplicate batch insert?
        #yield db.batch_insert(convId, "mConversations", {'meta':meta})
        people = base.EntitySet(participants)
        yield people.fetchData()
        value = myId
        data = {"entities": people}
        data["entities"].update({args['orgId']: args["org"]})
        data["orgId"] = args["orgId"]
        data["convId"] = convId
        data["message"] = body
        data["subject"] = subject
        data["_fromName"] = people[value].basic['name']
        users = set(participants) - set([myId])
        if users:
            yield notifications.notify(users, ":NM", myId, timeUUID, **data)

        if script:
            request.write("$$.dialog.close('msgcompose-dlg', true);$$.fetchUri('/messages');")

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        """Call functions to create a new conversation or post a reply to an
        existing conversation.

        Keyword Arguments:
        parent: The optional id of the conversation to which this message
            was posted.

        """
        parent = utils.getRequestArg(request, "parent") or None
        if parent:
            yield self._reply(request)
        else:
            yield self._createConversation(request)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listConversations(self, request):
        """Renders a time sorted list of coversations in a particular view.

        Keyword Arguments:
        filerType: The folder view which is to rendered. One of ['unread', 'all',
            'archive', 'trash'].
        start: The base64 encoded timeUUID of the starting conversation id of
            the page that needs to be rendered.

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        filterType = utils.getRequestArg(request, 'type')
        folder = self._folders[filterType] if filterType in self._folders else\
                                                         self._folders['inbox']
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        if script and landing:
            t.render(request, "message.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "message.mako", "layout",
                                landing, "#mainbar", "set", **args)

        unread = []
        convs = []
        users = set()
        count = 10
        fetchCount = count + 1
        nextPageStart = ''
        prevPageStart = ''

        cols = yield db.get_slice(myId, folder, reverse=True, start=start,
                                    count=fetchCount)
        for col in cols:
            x, convId = col.column.value.split(':')
            convs.append(convId)
            if x == 'u':
                unread.append(convId)
        if len(cols) == fetchCount:
            nextPageStart = utils.encodeKey(col.column.name)
            convs = convs[:count]

        ###XXX: try to avoid extra fetch
        cols = yield db.get_slice(myId, folder, count=fetchCount, start=start)
        if cols and len(cols) > 1 and start:
            prevPageStart = utils.encodeKey(cols[-1].column.name)

        cols = yield db.multiget_slice(convs, 'mConversations')
        conversations = utils.multiSuperColumnsToDict(cols)
        m = {}
        for convId in conversations:
            if not conversations[convId]:
                continue
            participants = conversations[convId]['participants'].keys()
            users.update(participants)
            conversations[convId]['people'] = participants
            conversations[convId]['read'] = str(int(convId not in unread))
            messageCount = yield db.get_count(convId, "mConvMessages")
            conversations[convId]['count'] = messageCount
            m[convId] = conversations[convId]

        users = base.EntitySet(users)
        yield users.fetchData()

        args.update({"view": "messages"})
        args.update({"messages": m})
        args.update({"people": users})
        args.update({"mids": convs})
        args.update({"menuId": "messages"})

        args.update({"filterType": filterType or "all"})
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            onload = """
                     $$.menu.selectItem('%s');
                     $('#mainbar .contents').removeClass("has-right");
                     """ % args["menuId"]
            t.renderScriptBlock(request, "message.mako", "conversations",
                                    landing, ".center-contents", "set", True,
                                    handlers={"onload": onload}, **args)
            yield utils.render_LatestCounts(request, landing)
        else:
            t.render(request, "message.mako", **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _members(self, request):
        """Allow a participant of a conversation to add or remove another user
        to the conversation.

        Keyword arguments:
        action: Either one of [add, remove]
        convId: The conversation to which this user wants to either add or
            remove another user.

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        action = utils.getRequestArg(request, "action")
        convId = utils.getRequestArg(request, 'parent') or None

        if not convId:
            raise errors.MissingParams([_('Conversation Id')])
        if action not in ('add', 'remove'):
            raise errors.InvalidRequest()

        if action == "add":
            yield self._addMembers(request)
        elif action == "remove":
            yield self._removeMembers(request)

        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv['participants'])
        people = base.EntitySet(participants)
        yield people.fetchData()

        args.update({"people": people})
        args.update({"conv": conv})
        args.update({"convId": convId})
        args.update({"view": "message"})
        if script:
            onload = """
                     $('#conversation_add_member').autocomplete({
                           source: '/auto/users',
                           minLength: 2,
                           select: function( event, ui ) {
                               $('#conversation_recipients').attr('value', ui.item.uid)
                           }
                      });
                     """
            t.renderScriptBlock(request, "message.mako", "right",
                                landing, ".right-contents", "set", True,
                                handlers={"onload": onload}, **args)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addMembers(self, request):
        """This method add a new user to this conversation.

        Keyword Arguments:
        newMembers: A list of members who will be added to this conversation.
        convId: The id of the conversation to which these new members will be
            added as participants.

        CF Changes:
        mConversations

        """
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        newMembers, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and newMembers):
            raise errors.MissingParams(['Recipient'])

        conv = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(conv)
        subject = conv['meta'].get('subject', None)
        participants = set(conv.get('participants', {}).keys())
        if not conv:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        #cols = yield db.multiget_slice(newMembers, "entities", ['basic'])
        #people = utils.multiSuperColumnsToDict(cols)
        people = base.EntitySet(newMembers)
        yield people.fetchData()
        newMembers = set([userId for userId in people.keys() \
                            if people[userId].basic and \
                               people[userId].basic["org"] == orgId])
        newMembers = newMembers - participants

        mailNotificants = participants - set([myId])
        toFetchEntities = mailNotificants.union([myId, orgId]).union(newMembers)
        entities = base.EntitySet(toFetchEntities)
        yield entities.fetchData()
        data = {"entities": entities}
        data["orgId"] = orgId
        data["convId"] = convId
        data["subject"] = subject
        data["_fromName"] = entities[myId].basic['name']
        if newMembers:
            data["message"] = conv["meta"]["snippet"]
            newMembers = dict([(userId, '') for userId in newMembers])
            yield db.batch_insert(convId, "mConversations",
                                    {'participants': newMembers})
            yield self._deliverMessage(convId, newMembers,
                                       conv['meta']['uuid'],
                                       conv['meta']['owner'])
            yield notifications.notify(newMembers, ":NM", myId, **data)
        if mailNotificants and newMembers:
            data["addedMembers"] = newMembers
            yield notifications.notify(mailNotificants, ":MA", myId, **data)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _removeMembers(self, request):
        """This method allows the current user to remove another participant
        to this conversation.

        Keyword Arguments:
        newMembers: A list of members who will be added to this conversation.
        convId: The id of the conversation to which these new members will be
            added as participants.

        CF Changes:
        mConversations
        latest

        """
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        members, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and  members):
            raise errors.MissingParams([])

        conv = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(conv)
        subject = conv['meta'].get('subject', None)
        participants = conv.get('participants', {}).keys()
        if not conv:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        cols = yield db.multiget_slice(members, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(cols)
        members = set([userId for userId in people if people[userId] and \
                          people[userId]["basic"]["org"] == orgId])
        members = members.intersection(participants)

        if len(members) == len(participants):
            members.remove(conv['meta']['owner'])

        deferreds = []
        if members:
            d = db.batch_remove({"mConversations": [convId]},
                                    names=members,
                                    supercolumn='participants')
            deferreds.append(d)

            cols = yield db.get_slice(convId, 'mConvFolders', members)
            cols = utils.supercolumnsToDict(cols)
            for recipient in cols:
                for folder in cols[recipient]:
                    cf = self._folders[folder] \
                        if folder in self._folders else folder
                    d = db.remove(recipient, cf, conv['meta']['uuid'])
                    deferreds.append(d)
            #update latest- messages-count
            deferreds.append(db.batch_remove({"latest": members},
                                             names=[conv['meta']['uuid']],
                                             supercolumn='messages'))
            if deferreds:
                yield deferreds

        mailNotificants = set(participants) - members - set([myId])
        if mailNotificants and members:
            toFetchEntities = mailNotificants.union([myId, orgId]).union(members)
            entities = base.EntitySet(toFetchEntities)
            yield entities.fetchData()
            data = {"entities": entities}
            data["orgId"] = orgId
            data["convId"] = convId
            data["removedMembers"] = members
            data["subject"] = subject
            data["_fromName"] = entities[myId].basic['name']
            yield notifications.notify(mailNotificants, ":MA", myId, **data)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _actions(self, request):
        """Perform an action on a conversation or a group of conversations.
        Update the UI based on the folder and the view that the user is in.

        Keyword arguments:
        convIds: A list of conversations upon which an action is to be taken.
        filterType: The folder view in which this action was taken.
        trash: A presence of this argument indicates that the action is to
            delete the selected conversations.
        archive: A presence of this argument indicates that the action is to
            archive the selected conversations.
        unread: A presence of this argument indicates that the action is to
            mark the selected conversations as unread.
        inbox: A presence of this argument indicates that the action is to
            move the selected conversations to inbox.
        view: one of [message, messages] indicates whether the user is
            performing action on a single conversation or multiple conversations.
        action: The actual action that the user wants to peform. One of
            ["inbox", "archive", "trash", "read", "unread"]. This is used
            if none of the above are mentioned.

        CF Changes:
        mConvFolders
        mUnreadConversations
        latest
        mAllConversations
        mDeletedConversations

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        convIds = utils.getRequestArg(request, 'selected', multiValued=True) or []
        filterType = utils.getRequestArg(request, "filterType") or "all"
        trash = utils.getRequestArg(request, "trash") or None
        archive = utils.getRequestArg(request, "archive") or None
        unread = utils.getRequestArg(request, "unread") or None
        inbox = utils.getRequestArg(request, "inbox") or None
        view = utils.getRequestArg(request, "view") or "messages"

        if trash:
            action = "trash"
        elif archive:
            action = "archive"
        elif unread:
            action = "unread"
        elif inbox:
            action = "inbox"
        else:
            action = utils.getRequestArg(request, "action")

        if convIds:
            if action in self._folders.keys():
                yield self._moveConversation(request, convIds, action)
            elif action == "read":
                cols = yield db.multiget_slice(convIds, "mConversations")
                convs = utils.multiSuperColumnsToDict(cols)
                for convId in convs:
                    conv = convs[convId]
                    if not conv:
                        raise errors.InvalidMessage(convId)
                    if myId not in conv.get('participants', {}):
                        raise errors.MessageAccessDenied(convId)
                    timeUUID = conv['meta']['uuid']

                    yield db.remove(myId, "mUnreadConversations", timeUUID)
                    yield db.remove(convId, "mConvFolders",
                                    'mUnreadConversations', myId)
                    yield db.remove(myId, "latest", timeUUID, "messages")

                    cols = yield db.get_slice(convId, "mConvFolders", [myId])
                    cols = utils.supercolumnsToDict(cols)
                    for folder in cols[myId]:
                        if folder in self._folders:
                            folder = self._folders[folder]
                        yield db.insert(myId, folder, "r:%s" % (convId), timeUUID)
                count = yield utils.render_LatestCounts(request)

            # Update the UI based on the actions and folder view.
            if action in ["inbox", "archive", "trash"]:
                if filterType != "unread":
                    request.write("$('%s').remove();" \
                                  % ','.join(['#thread-%s' % \
                                              convId for convId in convIds]))

                if view == "message":
                    reason = _("Message moved to %s" % (action.capitalize()))
                    if action == "archive":
                        reason = _("Message archived")

                    request.write("""$$.fetchUri('/messages?type=%s')
                                  ;$$.alerts.info("%s");""" \
                                    % (filterType, reason))
                else:
                    reason = _("Messages moved to %s" % (action.capitalize()))
                    request.write("""$('#thread-selector').attr('checked', false);
                                  $$.alerts.info("%s");""" % (reason))

            elif action == "unread":
                query_template = """
                              $('#thread-%s').removeClass('row-read').addClass('row-unread');
                              $('#thread-%s .messaging-read-icon').removeClass('messaging-read-icon').addClass('messaging-unread-icon');
                              $('#thread-%s .messaging-unread-icon').attr("title", "Mark this conversation as read");
                              $('#thread-%s .messaging-unread-icon')[0].onclick = function(event) { $.post('/ajax/messages/thread', 'action=read&selected=%s&filterType=%s', null, 'script') };
                              """
                query = "".join([query_template % (convId, convId, convId,
                                                   convId, convId, filterType) \
                                 for convId in convIds])

                if view == "message":
                    request.write("""$$.fetchUri('/messages');
                                  $$.alerts.info("%s");""" \
                                    % ("Message marked as unread"))
                else:
                    request.write(query)

            elif action == "read":
                # If we are in unread view, remove the conv else swap the styles
                if filterType != "unread":
                    query_template = """
                                  $('#thread-%s').removeClass('row-unread').addClass('row-read');
                                  $('#thread-%s .messaging-unread-icon').removeClass('messaging-unread-icon').addClass('messaging-read-icon');
                                  $('#thread-%s .messaging-read-icon').attr("title", "Mark this conversation as unread")
                                  $('#thread-%s .messaging-read-icon')[0].onclick = function(event) { $.post('/ajax/messages/thread', 'action=unread&selected=%s&filterType=%s', null, 'script') }
                                  """
                    query = "".join([query_template % (convId, convId, convId,
                                                       convId, convId, filterType) \
                                     for convId in convIds])
                    request.write(query)
                else:
                    request.write("$('%s').remove()" \
                                    % ','.join(['#thread-%s' \
                                            % convId for convId in convIds]))

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _moveConversation(self, request, convIds, toFolder):
        """Move a conversation or conversations from one folder to another.

        Keyword Arguments:
        convIds: List of conversation ids which need to be moved.
        toFolder: The final destination of the above conversations

        CF Changes:
        mConvFolders
        mUnreadConversations
        mAllConversations
        mDeletedConversations

        """
        myId = request.getSession(IAuthInfo).username

        convs = yield db.multiget_slice(convIds, "mConversations")
        convs = utils.multiSuperColumnsToDict(convs)
        for convId in convs:
            conv = convs.get(convId, {})
            if not conv:
                raise errors.InvalidMessage(convId)
            if myId not in conv.get('participants', {}):
                raise errors.MessageAccessDenied(convId)

            timeUUID = conv['meta']['uuid']
            val = "%s:%s" % ('u' if toFolder == 'unread' else 'r', convId)

            cols = yield db.get_slice(convId, 'mConvFolders', [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                cf = self._folders[folder] if folder in self._folders else folder
                if toFolder != 'unread':
                    if folder != 'mUnreadConversations':
                        col = yield db.get(myId, cf, timeUUID)
                        val = col.column.value
                        yield db.remove(myId, cf, timeUUID)
                        yield db.remove(convId, "mConvFolders", cf, myId)
                else:
                    yield db.insert(myId, cf, "u:%s" % (convId), timeUUID)

            if toFolder == 'unread':
                val = "u:%s" % (convId)
                yield db.insert(convId, 'mConvFolders', '',
                                    'mUnreadConversations', myId)
                yield db.insert(myId, 'mUnreadConversations', val, timeUUID)
            else:
                folder = self._folders[toFolder]
                yield db.insert(myId, folder, val, timeUUID)
                yield db.insert(convId, 'mConvFolders', '', folder, myId)

    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderConversation(self, request):
        """Render a conversation.

        Keyword arguments:
        convId: The id of the conversation that needs to be rendered.

        """
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convId = utils.getRequestArg(request, 'id', sanitize=False)
        if not convId:
            raise errors.MissingParams([])

        if script and landing:
            t.render(request, "message.mako", **args)

        if appchange and script:
            t.renderScriptBlock(request, "message.mako", "layout",
                                landing, "#mainbar", "set", **args)

        start = utils.getRequestArg(request, 'start') or ''
        start = utils.decodeKey(start)
        count = constants.MESSAGES_PER_PAGE

        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv.get('participants', {}).keys())
        nextPageStart = ''

        if not conv:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        timeUUID = conv['meta']['uuid']
        d1 = db.remove(myId, "mUnreadConversations", timeUUID)
        d2 = db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
        d3 = db.remove(myId, "latest", timeUUID, "messages")
        deferreds = [d1, d2, d3]
        yield defer.DeferredList(deferreds)
        deferreds = []
        cols = yield db.get_slice(convId, "mConvFolders", [myId])
        cols = utils.supercolumnsToDict(cols)
        for folder in cols[myId]:
            if folder in self._folders:
                folder = self._folders[folder]
            d = db.insert(myId, folder, "r:%s" % (convId), timeUUID)
            deferreds.append(d)

        inFolders = cols[myId].keys()
        #FIX: make sure that there will be an entry of convId in mConvFolders
        cols = yield db.get_slice(convId, "mConvMessages", start=start,
                                                            count=count + 1)
        mids = [col.column.value for col in cols]
        messages = yield db.multiget_slice(mids, "messages", ["meta"])
        messages = utils.multiSuperColumnsToDict(messages)

        if len(mids) == count + 1:
            nextPageStart = utils.encodeKey(cols[-1].column.name)
            mids = mids[:count]

        s = yield defer.DeferredList(deferreds)
        participants.update([messages[mid]['meta']['owner'] for mid in messages])
        people = base.EntitySet(participants)
        yield people.fetchData()

        args.update({"people": people})
        args.update({"conv": conv})
        args.update({"messageIds": mids})
        args.update({'messages': messages})
        args.update({"convId": convId})
        args.update({"view": "message"})
        args.update({"menuId": "messages"})
        args.update({"inFolders": inFolders})
        args.update({"nextPageStart": nextPageStart})

        if script:
            if not start:
                onload = """
                         $$.menu.selectItem("messages");
                         $('#mainbar .contents').addClass("has-right");
                         """
                t.renderScriptBlock(request, "message.mako", "center",
                                    landing, ".center-contents", "set", True,
                                    handlers={"onload": onload}, **args)

                onload = """
                         $$.messaging.initConversation();
                        """
                t.renderScriptBlock(request, "message.mako", "right",
                                    landing, ".right-contents", "set", True,
                                    handlers={"onload": onload}, **args)
                yield utils.render_LatestCounts(request, landing)
            else:
                t.renderScriptBlock(request, "message.mako", "conversation",
                                    landing, "#next-page-loader", "replace", **args)
        else:
            t.render(request, "message.mako", **args)

    def _renderComposer(self, request):
        """Render the New Message Composer.

        Keyword arguments:
        recipients: An optional list of userIds as recipients.
        subject: An optional subject line for the new message.
        body: An optional message for the recipients.

        """
        rcpts = utils.getRequestArg(request, 'recipients', True, True) or ''
        subject = utils.getRequestArg(request, 'subject', True, True) or ''
        body = utils.getRequestArg(request, 'body', False) or ''

        onload = "$$.messaging.initComposer();"
        t.renderScriptBlock(request, "message.mako", "composerDialog",
                            False, "#msgcompose-dlg", "set", True,
                            handlers={"onload": onload},
                            args=[rcpts, subject, body])
        return True

    @defer.inlineCallbacks
    def _messageActions(self, request):
        """Perform an action on a single message in a conversation

        Keyword arguments:
        messageId: The id of the message within a conversation.
        conversationId: The conversation to which this message belongs.
        action: A supported action that is to be performed on this message.

        """

        convId = utils.getRequestArg(request, 'convId')
        messageId = utils.getRequestArg(request, 'mId')
        myId = request.getSession(IAuthInfo).username
        action = utils.getRequestArg(request, 'action')

        if not (convId or messageId) or action != "delete":
            raise errors.MissingParams(["Conversation ID", "Message ID",
                                                                    "Action"])

        message = yield db.get_slice(messageId, "messages", ["meta"])
        message = utils.supercolumnsToDict(message)

        if message["meta"]["owner"] != myId:
            raise errors.MessageAccessDenied(convId)

        cols = yield db.get_slice(convId, "mConvMessages")
        mids = [col.column.value for col in cols]

        if messageId not in mids:
            raise errors.MessageAccessDenied(convId)
        else:
            tId = dict([[col.column.value, col.column.name] \
                            for col in cols])[messageId]

        if action == "delete":
            lastId = None
            if mids.index(messageId) == len(mids) - 1:
                mids.remove(messageId)
                if mids:
                    lastId = mids.pop()
            yield self._deleteMessage(request, messageId, convId, tId, lastId)

    @defer.inlineCallbacks
    def _deleteMessage(self, request, messageId, convId, tId, lastId=None):
        yield db.remove(convId, "mConvMessages", tId)
        yield db.remove(messageId, "messages")
        request.write("$$.messaging.removeMessage('%s');" % (messageId))
        if lastId:
            message = yield db.get_slice(lastId, "messages", ["meta"])
            message = utils.supercolumnsToDict(message)
            snippet = self._fetchSnippet(message["meta"]["body"])
            meta = {"snippet": snippet}
            yield db.batch_insert(convId, "mConversations", {'meta': meta})

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listConversations(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._renderConversation(request)
        elif segmentCount == 1 and request.postpath[0] == "files":
            d = self._renderFile(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._actions(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._composeMessage(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._actions(request)
        elif segmentCount == 1 and request.postpath[0] == "members":
            d = self._members(request)
        elif segmentCount == 1 and request.postpath[0] == "message":
            d = self._messageActions(request)

        return self._epilogue(request, d)
