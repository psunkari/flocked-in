import uuid
import random, re
import pytz, time, datetime
import email.utils

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from telephus.cassandra     import ttypes

from social             import Db, utils, base, auth, errors
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE


class MessagingResource(base.BaseResource):
    isLeaf = True
    _specialFolders = ["INBOX", "SENT", "DRAFTS", "TRASH", "ARCHIVES"]

    @defer.inlineCallbacks
    def _checkUserFolderACL(self, userId, folder):
        #Check if user owns the folder or has permission to access it(XXX)
        if folder.rfind(":") != -1 and folder.startswith(userId):
            defer.returnValue(True)
        else:
            if folder.upper() in self._specialFolders:
                folder = "%s:%s" %(myKey, folder.upper())
            try:
                yield Db.get(key=userId, column_family="mUserFolders",
                             super_column=folder)
            except ttypes.NotFoundException:
                defer.returnValue(False)
            else:
                defer.returnValue(True)

    @defer.inlineCallbacks
    def _threadActions(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        _validActions = ["delete", "star", "unstar", "read", "unread", "fullview"]
        parent = utils.getRequestArg(request, "parent") or None
        folder = utils.getRequestArg(request, "fid") or None
        delete = utils.getRequestArg(request, "delete")
        archive = utils.getRequestArg(request, "archive")
        isOtherActions = utils.getRequestArg(request, "other")
        action = utils.getRequestArg(request, "more")

        if folder:
            res = yield self._checkUserFolderACL(myKey, folder)
            if not res:
                request.redirect("/messages")
        else:
            request.redirect("/messages")

        mids = [parent]
        res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                      names=mids)
        res = utils.supercolumnsToDict(res, ordered=True)
        tids = [res[x]["timestamp"] for x in res.keys() if "timestamp" in res[x]]

        if len(tids) > 0 and folder:
            copyToFolder = ""
            if delete:
                copyToFolder = "%s:%s" %(myKey, "TRASH")
                yield self._copyToFolder(copyToFolder, mids, tids)
                yield self._deleteFromFolder(folder, tids)
            elif archive:
                copyToFolder = "%s:%s" %(myKey, "ARCHIVES")
                yield self._copyToFolder(copyToFolder, mids, tids)
                yield self._deleteFromFolder(folder, tids)
            elif isOtherActions:
                if action not in _validActions:
                    raise errors.InvalidParams()
                else:
                    if action == "star":
                        self._setFlagOnMessage(myKey, parent, "star", "1")
                    elif action == "unstar":
                        self._setFlagOnMessage(myKey, parent, "star", "0")
                    elif action == "read":
                        self._setFlagOnMessage(myKey, parent, "read", "1")
                    elif action == "unread":
                        self._setFlagOnMessage(myKey, parent, "read", "0")

            request.redirect("/messages?fid=%s"%(folder))
        else:
            request.redirect("/messages")

    @defer.inlineCallbacks
    def _setFlagOnMessage(self, user, message, flag, fValue):
        #XXX:Check if user has access to this message
        yield Db.insert(key=user, column_family="mUserMessages",
                        value=fValue, column=flag,
                        super_column=message)

    @defer.inlineCallbacks
    def _folderActions(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        folder = utils.getRequestArg(request, "fid")
        delete = utils.getRequestArg(request, "delete")
        archive = utils.getRequestArg(request, "archive")
        selected = request.args.get("selected", None)
        if selected and len(selected) > 0:
            # Selected are mids of the selected mails. We find their respective
            #   timestamps from mUserMessages and work from there
            res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                          names=selected)
            res = utils.supercolumnsToDict(res, ordered=True)
            tids = [res[x]["timestamp"] for x in res.keys()]
        else:
            request.redirect("/messages?fid=%s"%(folder))

        if folder:
            res = yield self._checkUserFolderACL(myKey, folder)
            if not res:
                request.redirect("/messages")
        else:
            request.redirect("/messages")

        if tids and folder and (delete or archive):
            #selected = yield Db.get_slice(folder, "mFolderMessages", selected)
            #mids = utils.columnsToDict(selected).values()
            #tids = utils.columnsToDict(selected).keys()
            copyToFolder = ""
            if delete:
                copyToFolder = "%s:%s" %(myKey, "TRASH")
            elif archive:
                copyToFolder = "%s:%s" %(myKey, "ARCHIVES")

            yield self._copyToFolder(copyToFolder, selected, tids)
            yield self._deleteFromFolder(folder, tids)
        request.redirect("/messages?fid=%s"%(folder))

    @defer.inlineCallbacks
    def _copyToFolder(self, destination, messages, timestamps):
        #XXX:Get the tids from mUserMessages and insert them
        message_map = {}
        for m in messages:
            message_map[timestamps[messages.index(m)]] = m
        yield Db.batch_insert(key=destination, column_family="mFolderMessages",
                              mapping=message_map)

    @defer.inlineCallbacks
    def _deleteFromFolder(self, folder, timestamps):
        cfmap = {"mFolderMessages":[folder]}
        yield Db.batch_remove(cfmap=cfmap, names=timestamps)

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        recipients, body, subject, parent = self._parseComposerArgs(request)
        if len(recipients) == 0:
            raise "No recipients specified"

        name = args['me']["basic"]["name"]
        email = args['me']["basic"]["emailId"]
        from_header = "%s <%s>" %(name, email)

        date_header, epoch = self._createDateHeader()
        new_message_id = str(utils.getUniqueKey()) + "@synovel.com"
        recipient_header, uids = yield self._createRecipientHeader(recipients)

        fid = utils.getRequestArg(request, 'fid') or "INBOX"
        # TODO: use the folderId from cookie
        #yield self._renderMessages(request)

        message = {
                      'From': from_header,
                      'To': recipient_header,
                      'Subject': subject,
                      'body':body,
                      'message-id':new_message_id,
                      'Date':date_header,
                      'references':"",
                      'irt':"",
                      'date_epoch': str(epoch)
                    }
        if parent:
            #XXX: Check if user has access to this message via acl
            parent = yield Db.get_slice(parent, "messages")
            parent = utils.columnsToDict(parent)
            if parent:
                message["references"] = parent["references"] + parent["message-id"]
                message['irt'] = parent["message-id"]
            else:
                #Throw an error
                parent = None
                raise errors.InvalidParams()


        yield Db.batch_insert(new_message_id, 'messages', message)
        yield self._deliverMessage(request, message, uids)
        request.redirect("/messages?fid=sent")

    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        parent = utils.getRequestArg(request, "parent")
        action = utils.getRequestArg(request, "action") or "reply"
        fid = request.args.get("fid", ["inbox"])[0]
        args.update({"fid":fid})

        folders = yield Db.get_slice(myKey, "mUserFolders")
        folders = utils.supercolumnsToDict(folders)
        args["folders"] = folders

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            renderScriptBlock(request, "message.mako", "layout",
                              landing, "#mainbar", "set", **args)

        if parent:
            #XXX: The current user should have the rights to view the message
            res = yield Db.multiget_slice(keys=[parent], column_family="messages")
            res = utils.multiColumnsToDict(res)
            if parent in res.keys():
                parent_msg = res[parent]
            else:
                parent_msg = None
            args.update({"parent_msg":parent_msg})
            if action == "forward":
                args.update({"view":"forward"})
            else:
                args.update({"view":"reply"})
            if script:
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)
        else:
            args.update({"view":"compose"})
            if script:
                yield renderScriptBlock(request, "message.mako", "center",
                                        landing, ".center-contents", "set", **args)
            else:
                yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderMessages(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)

        c_fid = None if (landing or appchange) else request.getCookie("fid")
        folderId = utils.getRequestArg(request, "fid") or c_fid or "INBOX"
        if folderId.upper() in self._specialFolders:
            folderId = "%s:%s" %(myKey, folderId.upper())

        if folderId != c_fid :
            request.addCookie('fid', folderId, path="/ajax/messages")

        yield self._checkStandardFolders(myKey)
        folders = yield Db.get_slice(myKey, "mUserFolders")
        folders = utils.supercolumnsToDict(folders)
        args["folders"] = folders

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            renderScriptBlock(request, "message.mako", "layout",
                              landing, "#mainbar", "set", **args)

        args.update({"fid":folderId})

        res = yield Db.get_slice(key=folderId, column_family="mFolderMessages",
                                 start=start, count=11, reverse=True)
        # Fetch the message-ids from mFolderMessages
        mids = utils.columnsToDict(res, ordered=True).values()
        tids = utils.columnsToDict(res, ordered=True).keys()
        tids = [utils.encodeKey(x) for x in tids]

        #The start key will help us go back and end key to go forward in paging
        startKey = tids[0] if len(tids) > 0 else 0
        endKey =  tids[-1] if len(tids) > 0 else 0
        if len(mids) < 11:
            endKey = 0
        args.update({"start":startKey, "end":endKey})

        # Count the total number of messages in this folder
        #XXX: We don't really need to show the total number of messages at the
        # moment.
        #res = yield Db.get_count(folder, "mFolderMessages")
        #args.update({"total":res})

        mids = mids[:-1] if len(mids) == 11 else mids

        if len(mids) > 0:
            res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                          names=mids)
            messageFlags = utils.supercolumnsToDict(res)
        else:
            messageFlags = {}

        res = yield Db.multiget_slice(keys=mids, column_family="messages")
        msgs = utils.multiColumnsToDict(res, ordered=True)
        for mid, msg in msgs.iteritems():
            people = yield self._generatePeopleInConversation(msg, myKey)
            msg.update({"people":people, "tid": tids[mids.index(mid)]})
            msg.update({"flags":messageFlags[mid]})
        args.update({"messages":msgs})
        args.update({"mids":mids})
        args.update({"view":"messages"})

        if script:
            yield renderScriptBlock(request, "message.mako", "center",
                                    landing, ".center-contents", "set", **args)
        else:
            yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderThread(self, request):
        #Based on the request, render a message or a conversation
        thread = request.args.get("id", [None])[0]
        folder = request.args.get("fid", [None])[0]
        #XXXBased on the user's preference, the id can be a message id or a
        # conversation id. In a conversation view, a single message can only be
        # viewed in the context of the entire conversation it belongs to. If
        # both conversation and message id are mentioned: the conversation will
        # be displayed and the message; if it belongs to the conversation will
        # be expanded.

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        conversationView = False

        folders = yield Db.get_slice(myKey, "mUserFolders")
        folders = utils.supercolumnsToDict(folders)
        args["folders"] = folders

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            renderScriptBlock(request, "message.mako", "layout",
                              landing, "#mainbar", "set", **args)

        if thread and folder:
            #XXX: the viewer needs to have the necessary acls to view this
            res = yield Db.get_slice(key=thread, column_family="messages")
            msgs = utils.columnsToDict(res)
            if len(msgs) > 0:
                #Mark the message as read.XXX: This will change when
                #   conversations are implemented
                yield Db.insert(key=myKey, column_family="mUserMessages",
                                value="1", column="read",
                                super_column=thread)
                res = yield Db.get_slice(key=myKey,
                                         column_family="mUserMessages",
                                         names=[thread])
                flags = utils.supercolumnsToDict(res)[thread]
                people = yield self._generatePeopleInConversation(msgs, myKey)
                msgs.update({"people":people})
                args.update({"message":msgs})
                args.update({"id":thread})
                args.update({"fid":folder})
                args.update({"flags":flags})
                args.update({"view":"message"})
                if script:
                    yield renderScriptBlock(request, "message.mako", "center",
                                            landing, ".center-contents", "set", **args)
                else:
                    yield render(request, "message.mako", **args)
            else:
                request.redirect("/messages?fid=%s"%(folder if folder else "inbox"))
        else:
            request.redirect("/messages?fid=%s"%(folder if folder else "inbox"))

    @defer.inlineCallbacks
    def _deliverMessage(self, request, message, recipients):
        #Deliver the message to the sender's collection
        myKey = auth.getMyKey(request)
        flags = {"read":"1"}
        folder = "%s:%s" %(myKey, "SENT")
        yield self._checkStandardFolders(myKey)
        yield self._deliverToUser(myKey, folder, message, flags)

        for recipient in recipients:
            #Deliver  to each recipient's Inbox
            #Check if the recipient has the standard folders
            folder = "%s:%s" %(recipient, "INBOX")
            yield self._checkStandardFolders(recipient)
            yield self._deliverToUser(recipient, folder, message, None)

    @defer.inlineCallbacks
    def _deliverToUser(self, userId, folderId, message, flags):

        isNewMessage = (message["irt"] == "")
        if isNewMessage:
            conversationId = utils.getUniqueKey()
        else:
            #XXX:What if the parent is deleted?Do we fetch the references?
            try:
                col = yield Db.get(userId, "mUserMessages",
                                   "conversation", message["irt"])
                conversationId = str(col.column.value)
            except ttypes.NotFoundException:
                conversationId = utils.getUniqueKey()

        flags = {} if flags is None else flags
        messageId = message["message-id"]
        timestamp = uuid.uuid1().bytes

        messageInfo = {}
        messageInfo["conversation"] = conversationId
        messageInfo["read"] = flags.get("read", "0")
        messageInfo["star"] = flags.get("star", "0")
        messageInfo["timestamp"] = timestamp

        yield Db.batch_insert(userId, "mUserMessages", {messageId: messageInfo})

        #Insert the new message to the folders cf
        yield Db.insert(folderId, "mFolderMessages", messageId, timestamp)

        #Insert this message into a new conversation
        yield Db.insert(conversationId, "mConversationMessages",
                        messageId, timestamp)

    def _preFormatBodyForReply(self, message, reply):
        body = message['body']
        sender = message['From']
        date = message['Date']
        #
        #On <RFC2822 formatted date> <Sender> wrote:
        #>Original message line1
        #>original message line2
        #>
        quoted_reply = "\n".join([">%s" %x for x in body.split('\n')]+['>'])
        prequotestring = "On %s, %s wrote" %(date, sender)
        new_reply = "%s\n\n%s\n%s" %(reply, prequotestring, quoted_reply)
        return new_reply

    def _createDateHeader(self):
        tz = pytz.timezone("Asia/Kolkata")
        dt = tz.localize(datetime.datetime.now())
        fmt_2822 = "%a, %d %b %Y %H:%M:%S %Z%z"
        date = dt.strftime(fmt_2822)
        epoch = time.mktime(dt.timetuple())
        return date, epoch

    @defer.inlineCallbacks
    def _createRecipientHeader(self, recipients):
        recipients_email = []
        for recipient in recipients:
            name, mailId = email.utils.parseaddr(recipient)
            if mailId is not '':
                recipients_email.append(mailId)
            else:
                raise errors.InvalidEmailId()

        res = yield Db.multiget_slice(recipients_email, "userAuth", ["user"])
        res = utils.multiColumnsToDict(res)

        if not all(res.values()):
            raise errors.InvalidEmailId()

        recipient_strings = []
        uids = [x['user'] for x in res.values() if 'user' in x]
        res = yield Db.multiget_slice(uids, 'entities', ["basic"])
        res = utils.multiSuperColumnsToDict(res)
        for uid in res.keys():
            recipient_strings.append("%s <%s>" %(res[uid]["basic"]["name"],
                                                 res[uid]["basic"]["emailId"]))
        recipient_header = ", ".join(recipient_strings)
        defer.returnValue((recipient_header, uids))

    def _parseComposerArgs(self, request):
        #Since we will deal with composer related forms.Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        parent = utils.getRequestArg(request, "parent") #TODO
        subject = utils.getRequestArg(request, "subject") or "Private message from XYZ"
        recipients = utils.getRequestArg(request, "recipients")
        recipients = re.sub(',\s+', ',', recipients).split(",")
        return recipients, body, subject, parent

    @defer.inlineCallbacks
    def _generatePeopleInConversation(self, message, myKey):
        sender = message["From"]
        to = message["To"]
        cc = message.get("Cc", "")
        #The owner of the message can see who he shared this message with.
        shared = ""
        people = re.sub(',\s+', ',', to+cc+shared).split(",")

        people_ids = []
        for p in people:
            rtuple = email.utils.parseaddr(p)
            remail = rtuple[1]
            people_ids.append(remail)

        res = yield Db.multiget_slice(keys=people_ids, column_family="userAuth")
        res = utils.multiColumnsToDict(res)
        uids = [x['user'] for x in res.values() if 'user' in x]
        res = yield Db.multiget_slice(keys=uids, column_family='entities')
        res = utils.multiSuperColumnsToDict(res)
        people = []
        for uid in res.keys():
            if uid == myKey:
                people.append("me")
            else:
                people.append(res[uid]["basic"]["name"])

        defer.returnValue(people)

    @defer.inlineCallbacks
    def _checkStandardFolders(self, userid):
        #Standard folders have the same key as their labels.
        try:
            yield Db.get(key=userid, column_family='mUserFolders',
                         super_column="%s:%s" %(userid, "INBOX"))
        except ttypes.NotFoundException:
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Inbox", column="label",
                            super_column="%s:%s" %(userid, "INBOX"))
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Sent", column="label",
                            super_column="%s:%s" %(userid, "SENT"))
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Trash", column="label",
                            super_column="%s:%s" %(userid, "TRASH"))
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Archives", column="label",
                            super_column="%s:%s" %(userid, "ARCHIVES"))
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Drafts", column="label",
                            super_column="%s:%s" %(userid, "DRAFTS"))

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderMessages(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._renderThread(request)

        return self._epilogue(request, d)

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._folderActions(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._composeMessage(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._threadActions(request)

        return self._epilogue(request, d)
