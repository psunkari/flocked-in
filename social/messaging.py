import uuid
import pickle
import re
import pytz, time, datetime
import mimetypes
from base64     import urlsafe_b64encode, urlsafe_b64decode
from email.header import Header

import boto
from telephus.cassandra import ttypes
from txaws.credentials import AWSCredentials
from txaws.s3 import client as s3Client
from boto.s3.connection import S3Connection
from boto.s3.connection import VHostCallingFormat, SubdomainCallingFormat

from twisted.internet   import defer
from twisted.web        import static, server

from social             import db, utils, base, errors, config, _, search
from social             import notifications
from social.relations   import Relation
from social.isocial     import IAuthInfo
from social.template    import render, renderScriptBlock
from social.logging     import profile, dump_args, log


class MessagingResource(base.BaseResource):
    isLeaf = True
    _folders = {'inbox': 'mAllConversations',
                'archive': 'mArchivedConversations',
                'trash': 'mDeletedConversations',
                'unread': 'mUnreadConversations'}

    def _formatAttachMeta(self, attachments):
        attach_meta = {}
        for attachmentId in attachments:
            timeuuid, fid, name, size, ftype = attachments[attachmentId]
            val = "%s:%s:%s:%s" %(utils.encodeKey(timeuuid), name, size, ftype)
            attach_meta[attachmentId] = val

        return attach_meta


    def _indexMessage(self, convId, messageId, myOrgId, meta, attachments, body):
        meta['type']="message"
        meta['body'] = body
        meta['parent'] = convId
        meta['timestamp'] = meta['date_epoch']
        meta = {"meta":meta}
        search.solr.updateMessage(messageId, meta, myOrgId, attachments)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _handleAttachments(self, request):
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
        authinfo = request.getSession(IAuthInfo)
        myId = authinfo.username
        myOrgId = authinfo.organization
        itemId = utils.getRequestArg(request, "id", sanitize=False)
        attachmentId = utils.getRequestArg(request, "fid", sanitize=False)
        version = utils.getRequestArg(request, "ver", sanitize=False)
        columns = ["meta", "attachments", "participants"]

        if not (itemId and attachmentId and version):
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

        try:
            version = utils.decodeKey(version)
        except TypeError:
            raise errors.InvalidAttachment(itemId, attachmentId, version)

        fileId, filetype, name = None, 'text/plain', 'file'
        owner = item["meta"]["owner"]
        try:
            cols = yield db.get(itemId, "item_files", version, attachmentId)
        except ttypes.NotFoundException:
            raise errors.InvalidAttachment(itemId, attachmentId, version)
        except ttypes.InvalidRequestException:
            raise errors.InvalidAttachment(itemId, attachmentId, version)

        cols = utils.columnsToDict([cols])
        tuuid, fileId, name, size, filetype = cols[version].split(':')

        files = yield db.get_slice(fileId, "files", ["meta"])
        files = utils.supercolumnsToDict(files)

        url = files['meta']['uri']
        defer.returnValue([owner, url, filetype, size, name])


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderFile(self, request):
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

        headers={'response-content-type':fileType,
                 'response-content-disposition':'attachment;filename=\"%s\"'%filename,
                 'response-expires':'0'}

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
                                     '%s/%s/%s' %(myOrgId, owner, url),
                                     response_headers=headers,
                                     force_http=True)

        request.setResponseCode(307)
        request.setHeader('Location', Location)


    def _parseComposerArgs(self, request):
        #Since we will deal with composer related forms. Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        if body:
            body = body.decode('utf-8').encode('utf-8', "replace")
        parent = utils.getRequestArg(request, "parent") #TODO
        subject = utils.getRequestArg(request, "subject") or ''
        if subject: subject.decode('utf-8').encode('utf-8', "replace")

        recipients = utils.getRequestArg(request, "recipients", sanitize=False)
        if recipients:
            recipients = re.sub(',\s+', ',', recipients).split(",")
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
        convFolderMap = {}
        userFolderMap = {}
        toNotify = {}
        toRemove = {'latest':[]}
        conv = yield db.get_slice(convId, "mConversations", ['meta'])
        conv = utils.supercolumnsToDict(conv)

        oldTimeUUID = conv['meta']['uuid']
        unread = "u:%s"%(convId)
        read = "r:%s"%(convId)

        cols = yield db.get_slice(convId, 'mConvFolders', recipients)
        cols = utils.supercolumnsToDict(cols)
        for recipient in recipients:
            deliverToInbox = True
            # for a new message, mConvFolders will be empty
            # so recipient may not necessarily be present in cols
            if recipient != owner:
                toNotify[recipient]= {'latest': {'messages':{timeUUID: convId}}}
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
                convFolderMap[recipient] = {'mAllConversations':{timeUUID:val}}
                userFolderMap[recipient]= {'mAllConversations':''}
                if recipient != owner:
                    convFolderMap[recipient]['mUnreadConversations'] = {timeUUID:unread}
                    userFolderMap[recipient]['mUnreadConversations'] = ''

            else:
                val = unread if recipient != owner else read
                convFolderMap[recipient] = {'mDeletedConversations':{timeUUID:val}}


        yield db.batch_mutate(convFolderMap)
        yield db.batch_insert(convId, "mConvFolders", userFolderMap)
        if toRemove['latest'] and oldTimeUUID != timeUUID:
            yield db.batch_remove(toRemove, names=[oldTimeUUID], supercolumn="messages")
        if toNotify:
            yield db.batch_mutate(toNotify)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _newMessage(self, ownerId, timeUUID, body, epoch):
        messageId = utils.getUniqueKey()
        meta =  { "owner": ownerId,
                 "timestamp": str(int(time.time())),
                 'date_epoch': str(epoch),
                 "body": body,
                 "uuid": timeUUID
                }
        yield db.batch_insert(messageId, "messages", {'meta':meta})
        defer.returnValue(messageId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _newConversation(self, ownerId, participants, meta, attachments):
        participants = dict ([(userId, '') for userId in participants])
        convId = utils.getUniqueKey()
        attach_meta = self._formatAttachMeta(attachments)
        yield db.batch_insert(convId, "mConversations", {"meta": meta,
                                                "participants": participants,
                                                "attachments":attach_meta})
        defer.returnValue(convId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _reply(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgKey']

        convId = utils.getRequestArg(request, 'id')
        recipients, body, subject, convId = self._parseComposerArgs(request)
        epoch = int(time.time())

        if not convId:
            raise errors.MissingParams([])

        cols = yield db.get_slice(convId, "mConversations", ['meta', 'participants'])
        cols = utils.supercolumnsToDict(cols)
        subject = cols['meta'].get('subject', None)
        participants = cols.get('participants', {}).keys()
        if not cols:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet":snippet}

        attachments = yield self._handleAttachments(request)
        attach_meta = self._formatAttachMeta(attachments)

        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)
        yield db.batch_insert(convId, "mConversations",
                              {'meta':meta, 'attachments':attach_meta})

        # Currently, we don't support searching for private messages
        # self._indexMessage(convId, messageId, myOrgId, meta, attachments, body)

        for file, file_meta in attachments.iteritems():
            timeuuid, fid, name, size, ftype  = file_meta
            val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
            yield db.insert(convId, "item_files", val, timeuuid, file)

        #XXX:We currently only fetch the message we inserted. Later we may fetch
        # all messages delivered since we last rendered the conversation
        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv['participants'])
        mids = [messageId]
        messages = yield db.multiget_slice(mids, "messages", ["meta"])
        messages = utils.multiSuperColumnsToDict(messages)
        participants.update([messages[mid]['meta']['owner'] for mid in messages])

        people = yield db.multiget_slice(participants, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)

        value = myId
        data = {"entities": people}
        data["entities"].update({args['orgKey']: args["org"]})
        data["orgId"] = args["orgKey"]
        data["convId"] = convId
        data["message"] = body
        data["subject"] = subject
        data["_fromName"] = people[value]['basic']['name']

        users = participants - set([myId])
        if users:
            yield notifications.notify(users, ":MR", value, timeUUID, **data)

        args.update({"people":people})
        args.update({"messageIds": mids})
        args.update({'messages': messages})
        if script:
            onload = """
                        $('.conversation-reply').attr('value', '');
                        $('#msgreply-attach-uploaded').empty();
                     """
            yield renderScriptBlock(request, "message.mako",
                                            "render_conversation_messages",
                                            landing,
                                            ".conversation-messages-wrapper",
                                            "append", True,
                                            handlers={"onload":onload}, **args)

        #Update the right side bar with any attachments the user uploaded
        args.update({"conv":conv})
        participants = set(conv['participants'])
        people = yield db.multiget_slice(participants, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)

        args.update({"people":people})
        args.update({"conv":conv})
        args.update({"id":convId})
        args.update({"view":"message"})
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
            yield renderScriptBlock(request, "message.mako", "right",
                                    landing, ".right-contents", "set", True,
                                    handlers={"onload":onload}, **args)

        else:
            request.redirect('/messages')
            request.finish()


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _createConversation(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        myOrgId = args['orgKey']
        epoch = int(time.time())

        recipients, body, subject, parent = self._parseComposerArgs(request)
        filterType = utils.getRequestArg(request, "filterType") or None

        if not parent and not recipients:
            raise errors.MissingParams(['Recipients'])

        if not subject and not body:
            raise errors.MissingParams(['Both subject and message'])

        cols = yield db.multiget_slice(recipients, "entities", ['basic'])
        recipients = utils.multiSuperColumnsToDict(cols)
        recipients = set([userId for userId in recipients if recipients[userId]])
        if not recipients:
            raise errors.MissingParams(['Recipients'])

        recipients.add(myId)
        participants = list(recipients)

        timeUUID = uuid.uuid1().bytes
        snippet = self._fetchSnippet(body)
        meta = {'uuid': timeUUID, 'date_epoch': str(epoch), "snippet": snippet,
                'subject':subject, "owner":myId,
                "timestamp": str(int(time.time()))}
        attachments = yield self._handleAttachments(request)

        convId = yield self._newConversation(myId, participants, meta, attachments)
        messageId = yield self._newMessage(myId, timeUUID, body, epoch)
        yield self._deliverMessage(convId, participants, timeUUID, myId)
        yield db.insert(convId, "mConvMessages", messageId, timeUUID)

        for file, file_meta in attachments.iteritems():
            timeuuid, fid, name, size, ftype  = file_meta
            val = "%s:%s:%s:%s:%s" %(utils.encodeKey(timeuuid), fid, name, size, ftype)
            yield db.insert(convId, "item_files", val, timeuuid, file)
        self._indexMessage(convId, messageId, myOrgId, meta, attachments, body)

        #XXX: Is this a duplicate batch insert?
        #yield db.batch_insert(convId, "mConversations", {'meta':meta})
        people = yield db.multiget_slice(participants, "entities", ["basic"])
        people = utils.multiSuperColumnsToDict(people)
        value = myId
        data = {"entities": people}
        data["entities"].update({args['orgKey']: args["org"]})
        data["orgId"] = args["orgKey"]
        data["convId"] = convId
        data["message"] = body
        data["subject"] = subject
        data["_fromName"] = people[value]['basic']['name']
        users = set(participants) - set([myId])
        if users:
            yield notifications.notify(users, ":NM", myId, timeUUID, **data)

        if script:
            request.write("$('#composer').empty();$$.fetchUri('/messages');")


    @defer.inlineCallbacks
    def _composeMessage(self, request):
        parent = utils.getRequestArg(request, "parent") or None
        if parent:
            yield self._reply(request)
        else:
            yield self._createConversation(request)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _listConversations(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        filterType = utils.getRequestArg(request, 'type')
        folder = self._folders[filterType] if filterType in self._folders else\
                                                         self._folders['inbox']
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        unread = []
        convs = []
        users = set()
        count = 10
        fetchCount = count + 1
        nextPageStart = ''
        prevPageStart = ''

        cols = yield db.get_slice(myKey, folder, reverse=True, start=start, count=fetchCount)
        for col in cols:
            x, convId = col.column.value.split(':')
            convs.append(convId)
            if x == 'u':
                unread.append(convId)
        if len(cols) == fetchCount:
            nextPageStart = utils.encodeKey(col.column.name)
            convs = convs[:count]

        ###XXX: try to avoid extra fetch
        cols = yield db.get_slice(myKey, folder, count=fetchCount, start=start)
        if cols and len(cols)>1 and start:
            prevPageStart = utils.encodeKey(cols[-1].column.name)


        cols = yield db.multiget_slice(convs, 'mConversations')
        conversations = utils.multiSuperColumnsToDict(cols)
        m={}
        for convId in conversations:
            if not conversations[convId]:
                continue
            participants = conversations[convId]['participants'].keys()
            users.update(participants)
            conversations[convId]['people'] = participants
            conversations[convId]['read'] = str(int(convId not in unread))
            messageCount = yield db.get_count(convId, "mConvMessages")
            conversations[convId]['count'] = messageCount
            m[convId]=conversations[convId]

        users = yield db.multiget_slice(users, 'entities', ['basic'])
        users = utils.multiSuperColumnsToDict(users)


        args.update({"view":"messages"})
        args.update({"messages":m})
        args.update({"people":users})
        args.update({"mids": convs})
        args.update({"menuId": "messages"})

        args.update({"filterType": filterType or "all"})
        args['nextPageStart'] = nextPageStart
        args['prevPageStart'] = prevPageStart

        if script:
            onload = """
                     $$.menu.selectItem('%s');
                     $('#mainbar .contents').removeClass("has-right");
                     """ %args["menuId"]
            yield renderScriptBlock(request, "message.mako", "render_conversations", landing,
                                    ".center-contents", "set", True,
                                    handlers={"onload": onload}, **args)
            yield utils.render_LatestCounts(request, landing)
        else:
            yield render(request, "message.mako", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _members(self, request):
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
        people = yield db.multiget_slice(participants, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)

        args.update({"people":people})
        args.update({"conv":conv})
        args.update({"id":convId})
        args.update({"view":"message"})
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
            yield renderScriptBlock(request, "message.mako", "right",
                                    landing, ".right-contents", "set", True,
                                    handlers={"onload":onload}, **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _addMembers(self, request):
        myId = request.getSession(IAuthInfo).username
        orgId = request.getSession(IAuthInfo).organization
        newMembers, body, subject, convId = self._parseComposerArgs(request)

        if not (convId and newMembers):
            raise errors.MissingParams([])

        conv = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(conv)
        subject = conv['meta'].get('subject', None)
        participants =  set(conv.get('participants', {}).keys())
        if not conv:
            raise errors.InvalidMessage(convId)
        if myId not in participants:
            raise errors.MessageAccessDenied(convId)

        cols = yield db.multiget_slice(newMembers, "entities", ['basic'])
        newMembers = set([userId for userId in cols if cols[userId]])
        newMembers = newMembers - participants

        mailNotificants = participants - set([myId])
        toFetchEntities = mailNotificants.union([myId, orgId]).union(newMembers)
        entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
        entities = utils.multiSuperColumnsToDict(entities)
        data = {"entities": entities}
        data["orgId"] = orgId
        data["convId"] = convId
        data["subject"] = subject
        data["_fromName"] = entities[myId]['basic']['name']
        if newMembers:
            data["message"] = conv["meta"]["snippet"]
            newMembers = dict([(userId, '') for userId in newMembers])
            yield db.batch_insert(convId, "mConversations", {'participants':newMembers})
            yield self._deliverMessage(convId, newMembers, conv['meta']['uuid'], conv['meta']['owner'])
            yield notifications.notify(newMembers, ":NM", myId, **data)
        if mailNotificants and newMembers:
            data["addedMembers"] = newMembers
            yield notifications.notify(mailNotificants, ":MA", myId, **data)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _removeMembers(self, request):
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
        members = set([userId for userId in cols if cols[userId]])
        members = members.intersection(participants)

        if len(members) == len(participants):
            members.remove(conv['meta']['owner'])

        deferreds = []
        if members:
            d =  db.batch_remove({"mConversations":[convId]},
                                    names=members,
                                    supercolumn='participants')
            deferreds.append(d)

            cols = yield db.get_slice(convId, 'mConvFolders', members)
            cols = utils.supercolumnsToDict(cols)
            for recipient in cols:
                for folder in cols[recipient]:
                    cf = self._folders[folder] if folder in self._folders else folder
                    d = db.remove(recipient, cf, conv['meta']['uuid'])
                    deferreds.append(d)
            #update latest- messages-count
            deferreds.append(db.batch_remove({"latest":members},
                                             names=[conv['meta']['uuid']],
                                             supercolumn='messages'))
            if deferreds:
                yield deferreds

        mailNotificants = set(participants) - members -set([myId])
        if mailNotificants and members:
            toFetchEntities = mailNotificants.union([myId, orgId]).union(members)
            entities = yield db.multiget_slice(toFetchEntities, "entities", ["basic"])
            entities = utils.multiSuperColumnsToDict(entities)
            data = {"entities": entities}
            data["orgId"] = orgId
            data["convId"] = convId
            data["removedMembers"] = members
            data["subject"] = subject
            data["_fromName"] = entities[myId]['basic']['name']
            yield notifications.notify(mailNotificants, ":MA", myId, **data)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _actions(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        convIds = utils.getRequestArg(request, 'selected', multiValued=True) or []
        filterType = utils.getRequestArg(request, "filterType") or "all"
        trash = utils.getRequestArg(request, "trash") or None
        archive = utils.getRequestArg(request, "archive") or None
        unread = utils.getRequestArg(request, "unread") or None
        inbox = utils.getRequestArg(request, "inbox") or None
        view = utils.getRequestArg(request, "view") or "messages"

        if trash:action = "trash"
        elif archive:action = "archive"
        elif unread:action = "unread"
        elif inbox:action = "inbox"
        else:action = utils.getRequestArg(request, "action")

        if convIds:
            if action in self._folders.keys():
                yield self._moveConversation(request, convIds, action)
            elif action == "read":
                #Remove it from unreadIndex and mark it as unread in all other
                # folders
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
                    yield db.remove(convId, "mConvFolders", 'mUnreadConversations', myId)
                    yield db.remove(myId, "latest", timeUUID, "messages")

                    cols = yield db.get_slice(convId, "mConvFolders", [myId])
                    cols = utils.supercolumnsToDict(cols)
                    for folder in cols[myId]:
                        if folder in self._folders:
                            folder = self._folders[folder]
                        yield db.insert(myId, folder, "r:%s"%(convId), timeUUID)
                count = yield utils.render_LatestCounts(request)

        if not self._ajax:
            #Not all actions on message(s) happen over ajax, for them do a redirect
            request.redirect("/messages?type=%s" %filterType)
            request.finish()
        elif self._ajax and len(convIds) > 0:
            #For all actions other than read/unread, since the action won't be
            # available to the user in same view; i.e, archive won't be on
            # archive view, we can simply remove the conv.
            if action in ["inbox", "archive", "trash"]:
                if filterType != "unread":
                    request.write("$('%s').remove();" %','.join(['#thread-%s' %convId for convId in convIds]))
                if view == "message":
                    reason = _("Message has been moved to the %s" %(action.capitalize()))
                    if action == "archive":
                        reason = _("Message has been archived")

                    request.write("""$$.fetchUri('/messages?type=%s');$$.alerts.info("%s");""" %(filterType, _(reason)))
            elif action == "unread":
                query_template = """
                              $('#thread-%s').removeClass('row-read').addClass('row-unread');
                              $('#thread-%s .messaging-read-icon').removeClass('messaging-read-icon').addClass('messaging-unread-icon');
                              $('#thread-%s .messaging-unread-icon').attr("title", "Mark this conversation as read");
                              $('#thread-%s .messaging-unread-icon')[0].onclick = function(event) { $.post('/ajax/messages/thread', 'action=read&selected=%s&filterType=%s', null, 'script') };
                              """
                query = "".join([query_template % (convId, convId, convId, convId, convId, filterType) for convId in convIds])

                if view == "message":
                    request.write("""$$.fetchUri('/messages');$$.alerts.info("%s");""" %("Message has been marked as unread"))
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
                    query = "".join([query_template % (convId, convId, convId, convId, convId, filterType) for convId in convIds])
                    request.write(query)
                else:
                    request.write("$('%s').remove()" %','.join(['#thread-%s' %convId for convId in convIds]))


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _moveConversation(self, request, convIds, toFolder):
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
            val = "%s:%s"%( 'u' if toFolder == 'unread' else 'r', convId)

            cols = yield db.get_slice(convId, 'mConvFolders', [myId])
            cols = utils.supercolumnsToDict(cols)
            for folder in cols[myId]:
                cf = self._folders[folder] if folder in self._folders else folder
                if toFolder!='unread':
                    if folder!= 'mUnreadConversations':
                        col = yield db.get(myId, cf, timeUUID)
                        val = col.column.value
                        yield db.remove(myId, cf, timeUUID)
                        yield db.remove(convId, "mConvFolders", cf, myId)
                else:
                        yield db.insert(myId, cf, "u:%s"%(convId), timeUUID)

            if toFolder == 'unread':
                val = "u:%s"%(convId)
                yield db.insert(convId, 'mConvFolders', '', 'mUnreadConversations', myId)
                yield db.insert(myId, 'mUnreadConversations', val, timeUUID)
            else:
                folder = self._folders[toFolder]
                yield db.insert(myId, folder, val, timeUUID)
                yield db.insert(convId, 'mConvFolders', '', folder, myId)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderConversation(self, request):
        (appchange, script, args, myId) = yield self._getBasicArgs(request)
        landing = not self._ajax
        convId = utils.getRequestArg(request, 'id', sanitize=False)
        if not convId:
            raise errors.MissingParams([])

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                              landing, "#mainbar", "set", **args)

        cols = yield db.get_slice(convId, "mConversations")
        conv = utils.supercolumnsToDict(cols)
        participants = set(conv.get('participants', {}).keys())
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
            d = db.insert(myId, folder, "r:%s"%(convId), timeUUID)
            deferreds.append(d)

        inFolders =  cols[myId].keys()
        #FIX: make sure that there will be an entry of convId in mConvFolders
        cols = yield db.get_slice(convId, "mConvMessages")
        mids = [col.column.value for col in cols]
        messages = yield db.multiget_slice(mids, "messages", ["meta"])
        messages = utils.multiSuperColumnsToDict(messages)

        participants.update([messages[mid]['meta']['owner'] for mid in messages])
        people = yield db.multiget_slice(participants, "entities", ['basic'])
        people = utils.multiSuperColumnsToDict(people)
        s = yield defer.DeferredList(deferreds)

        args.update({"people":people})
        args.update({"conv":conv})
        args.update({"messageIds": mids})
        args.update({'messages': messages})
        args.update({"id":convId})
        args.update({"flags":{}})
        args.update({"view":"message"})
        args.update({"menuId": "messages"})
        args.update({"inFolders":inFolders})

        if script:
            onload = """
                     $$.menu.selectItem("messages");
                     $('#mainbar .contents').addClass("has-right");
                     $('.conversation-reply').autogrow();
                     $('#message-reply-form').html5form({messages: 'en'});
                     """
            renderMessage = renderScriptBlock(request, "message.mako", "render_conversation",
                                    landing, ".center-contents", "set", True,
                                    handlers={"onload":onload}, **args)

            onload = """
                     $$.files.init('msgreply-attach');
                     $('#conversation_add_member').autocomplete({
                           source: '/auto/users',
                           minLength: 2,
                           select: function( event, ui ) {
                               $('#conversation_recipients').attr('value', ui.item.uid)
                           }
                      });
                    """
            renderParticipants = renderScriptBlock(request, "message.mako", "right",
                                    landing, ".right-contents", "set", True,
                                    handlers={"onload":onload}, **args)
            renderCounts = utils.render_LatestCounts(request, landing)
            yield defer.DeferredList([renderMessage, renderParticipants, renderCounts])
        else:
            yield render(request, "message.mako", **args)


    @profile
    @defer.inlineCallbacks
    @dump_args
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        args.update({"view":"compose"})

        if script and landing:
            yield render(request, "message.mako", **args)

        if script:
            onload = """
                    $$.messaging.autoFillUsers();
                    $('.conversation-composer-field-body').autogrow();
                    $$.files.init('msgcompose-attach');
                     """
            yield renderScriptBlock(request, "message.mako", "render_composer",
                                    landing, "#composer", "set", True,
                                    handlers={"onload":onload}, **args)
        else:
            yield render(request, "message.mako", **args)


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._listConversations(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._renderConversation(request)
        elif segmentCount == 1 and request.postpath[0] == "file":
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

        return self._epilogue(request, d)
