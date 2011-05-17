import uuid
import random, re
import pytz, time, datetime
from email.utils import parseaddr
from email.header import make_header

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log
from twisted.cred.error import Unauthorized

from telephus.cassandra     import ttypes

from social             import Db, utils, base, auth, errors, _, __
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE


class MessagingResource(base.BaseResource):
    isLeaf = True
    _specialFolders = ["INBOX", "SENT", "DRAFTS", "TRASH", "ARCHIVES"]

    @defer.inlineCallbacks
    def _checkUserFolderACL(self, userId, folder):
        #Check if user owns the folder or has permission to access it(XXX)
        res = yield Db.get_slice(folder, "mFolders", ["meta"])
        res = utils.supercolumnsToDict(res)
        if "meta" in res.keys():
            folderMeta = res["meta"]
        else:
            defer.returnValue(False)
        if userId == folderMeta["owner"]:
            defer.returnValue(True)
        else:
            #TODO:Check in the ACL if this user has access
            acl = folderMeta["acl"]
            defer.returnValue(False)

    @defer.inlineCallbacks
    def _checkUserHasMessageAccess(self, userId, messageId):
        #Check if user owns the message or has permission to access it(XXX)
        try:
            yield Db.get(key=userId, column_family="mUserMessages",
                         super_column=messageId)
        except ttypes.NotFoundException:
            defer.returnValue(False)
        else:
            defer.returnValue(True)

    @defer.inlineCallbacks
    def _threadActions(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax

        _validActions = ["delete", "star", "unstar", "read", "unread",
                         "fullview", "archive", "reply", "replytoall",
                         "forward"]
        message = utils.getRequestArg(request, "message") or None
        folderId = utils.getRequestArg(request, "fid") or None
        delete = utils.getRequestArg(request, "delete") or None
        archive = utils.getRequestArg(request, "archive") or None
        unread = utils.getRequestArg(request, "unread") or None
        if delete:action = "delete"
        elif archive:action = "archive"
        elif unread:action = "unread"
        else:action = utils.getRequestArg(request, "action")

        if action not in _validActions:
            raise
        if not (message or folderId):
            raise

        res = yield self._checkUserHasMessageAccess(myKey, message)
        if not res:
            raise Unauthorized

        res = yield self._checkUserFolderACL(myKey, folderId)
        if not res:
            request.redirect("/messages")

        mids = [message]
        res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                      names=mids)
        res = utils.supercolumnsToDict(res, ordered=True)
        mids = res.keys()
        tids = []
        for mId in mids:
            tids.append(res[mId]["timestamp"])

        tids = [res[x]["timestamp"] for x in res.keys() if "timestamp" in res[x]]

        if len(tids) > 0 and folderId:
            folders = yield self._getFolders(myKey)
            copyToFolder = ""
            if action == "delete":
                copyToFolder = self._getSpecialFolder(myKey, folders, "TRASH")
                if folderId != copyToFolder:
                    yield self._copyToFolder(copyToFolder, mids, tids)
                yield self._deleteFromFolder(folderId, mids, tids)
            elif action == "archive":
                copyToFolder = self._getSpecialFolder(myKey, folders, "ARCHIVES")
                if folderId != copyToFolder:
                    yield self._copyToFolder(copyToFolder, mids, tids)
                    yield self._deleteFromFolder(folderId, mids, tids)
            elif action == "star":
                yield self._setFlagOnMessage(myKey, message, "star", "1")
            elif action == "unstar":
                yield self._setFlagOnMessage(myKey, message, "star", "0")
            elif action == "read":
                yield self._setFlagOnMessage(myKey, message, "read", "1")
            elif action == "unread":
                yield self._setFlagOnMessage(myKey, message, "read", "0")
            if action in ["star", "unstar"]:
                if script:
                    args.update({"action":action, "mid":message, "fid":folderId})
                    yield renderScriptBlock(request, "message.mako",
                                            "render_message_headline_star",
                                            landing,
                                            "span.message-headline-star",
                                            "replace", **args)
                else:
                    request.redirect("/messages/thread?id=%s&fid=%s" %(message, folderId))
            else:
                request.redirect("/messages?fid=%s"%(folderId))
        else:request.redirect("/messages")

    @defer.inlineCallbacks
    def _setFlagOnMessage(self, user, message, flag, fValue):
        hasAccess = yield self._checkUserHasMessageAccess(user, message)
        if not hasAccess:
            raise Unauthorized

        yield Db.insert(key=user, column_family="mUserMessages",
                        value=fValue, column=flag,
                        super_column=message)

    @defer.inlineCallbacks
    def _folderActions(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        _validActions = ["delete", "star", "unstar", "read", "unread",
                         "fullview", "archive", "reply", "replytoall",
                         "forward"]
        folderId = utils.getRequestArg(request, "fid") or None
        delete = utils.getRequestArg(request, "delete")
        archive = utils.getRequestArg(request, "archive")
        selected = request.args.get("selected", None)
        tids = None
        if delete:action = "delete"
        elif archive:action = "archive"
        else:action = utils.getRequestArg(request, "action")

        if action not in _validActions:
            raise
        if not (selected or folderId):
            raise

        #TODO: Check if user has access to all the selected ids

        if selected and len(selected) > 0:
            # Selected are mids of the selected mails. We find their respective
            #   timestamps from mUserMessages and work from there
            res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                          names=selected)
            res = utils.supercolumnsToDict(res, ordered=True)
            selected = res.keys()
            tids = []
            for mId in selected:
                tids.append(res[mId]["timestamp"])
        else:
            request.redirect("/messages?fid=%s"%(folderId))
            request.finish()

        if folderId:
            res = yield self._checkUserFolderACL(myKey, folderId)
            if not res:
                raise
        else:
            request.redirect("/messages")
            request.finish()

        if tids and folderId:
            folders = yield self._getFolders(myKey)
            copyToFolder = ""
            if action=="delete":
                copyToFolder = self._getSpecialFolder(myKey, folders, "TRASH")
                if copyToFolder != folderId:
                    yield self._copyToFolder(copyToFolder, selected, tids)
                yield self._deleteFromFolder(folderId, selected, tids)
            elif action=="archive":
                copyToFolder = self._getSpecialFolder(myKey, folders, "ARCHIVES")
                yield self._copyToFolder(copyToFolder, selected, tids)
                if copyToFolder != folderId:
                    yield self._deleteFromFolder(folderId, selected, tids)
            elif action == "star":
                yield self._setFlagOnMessage(myKey, selected[0], "star", "1")
            elif action == "unstar":
                yield self._setFlagOnMessage(myKey, selected[0], "star", "0")
            elif action == "read":
                yield self._setFlagOnMessage(myKey, selected[0], "read", "1")
            elif action == "unread":
                yield self._setFlagOnMessage(myKey, selected[0], "read", "0")
            if action in ["star", "unstar"]:
                if script:
                    mid = selected[0]
                    args.update({"mid":mid})
                    res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                                  names=[mid])
                    messageFlags = utils.supercolumnsToDict(res)
                    res = yield Db.get_slice(key=mid, column_family="messages")
                    msgs = utils.columnsToDict(res, ordered=True)
                    people, myself = yield self._generatePeopleInConversation(msgs, myKey)
                    msgs.update({"people":people})
                    msgs.update({"flags":messageFlags[mid]})
                    msgs.update({"myself":myself})
                    args.update({"thread":msgs})
                    args.update({"fid":folderId})
                    yield renderScriptBlock(request, "message.mako", "messages_layout",
                                            landing,
                                            "#thread-%s" %(mid.replace(".", "\\.")\
                                                           .replace("@", "\\@")),
                                            "replace", **args)
                else:
                    request.redirect("/messages?fid=%s" %folderId)
                    request.finish()
            else:
                request.redirect("/messages?fid=%s" %folderId)
                request.finish()
        else:
            #XXX: instead of redirecting, we should render partly
            request.redirect("/messages")
            request.finish()

    @defer.inlineCallbacks
    def _copyToFolder(self, destination, messages, timestamps):
        message_map = {}
        for m in messages:
            message_map[timestamps[messages.index(m)]] = m
            yield Db.insert(key=m, column_family="mInFolders",
                                  column=destination, value="")
        yield Db.batch_insert(key=destination, column_family="mFolderMessages",
                              mapping=message_map)

    @defer.inlineCallbacks
    def _deleteFromFolder(self, folder, messages, timestamps):
        cfmap = {"mFolderMessages":[folder]}
        yield Db.batch_remove(cfmap=cfmap, names=timestamps)
        for m in messages:
            yield Db.remove(key=m, column_family="mInFolders", column=folder)
            res = yield Db.get_count(key=m, column_family="mInFolders")

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        #folderId = utils.getRequestArg(request, 'fid') or None

        name = args['me']["basic"]["name"]
        email = args['me']["basic"]["emailId"]
        from_header = "%s <%s>" %(name, email)

        recipients, body, subject, parent = self._parseComposerArgs(request)
        if not subject:
            subject = u"Private message from %s" %(name)

        date_header, epoch = self._createDateHeader()
        new_message_id = str(utils.getUniqueKey()) + "@synovel.com"
        try:
            recipient_header, uids = yield self._createRecipientHeader(recipients)
        except Exception:
            request.redirect("/messages/write")
        else:
            message = {
                          'From': from_header,
                          'To': recipient_header,
                          'Subject': subject,
                          'body': body,
                          'message-id':new_message_id,
                          'Date':date_header,
                          'references':"",
                          'irt':"",
                          'date_epoch': str(epoch),
                          'imap_subject': str(make_header([(subject, 'utf-8')])),
                          'timestamp': uuid.uuid1().bytes
                        }
            if parent:
                hasAccess = yield self._checkUserHasMessageAccess(myKey, parent)
                if not hasAccess:
                    raise Unauthorized

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
            request.redirect("/messages")

    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        parent = utils.getRequestArg(request, "parent")
        action = utils.getRequestArg(request, "action") or "reply"
        folderId = utils.getRequestArg(request, "fid") or None

        folders = yield self._getFolders(myKey)
        if folderId is None:
            #Find the Inbox of this user and set it.
            folderId = self._getSpecialFolder(myKey, folders)
        else:
            # Make sure user has access to the folder
            res = yield self._checkUserFolderACL(myKey, folderId)
            if not res:
                request.redirect("/messages")

        args["folders"] = folders
        args.update({"fid":folderId})

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if parent:
            hasAccess = yield self._checkUserHasMessageAccess(myKey, parent)
            if not hasAccess:
                raise Unauthorized

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

        back = utils.getRequestArg(request, "back") == "True"
        start = utils.getRequestArg(request, "start") or ''
        start = utils.decodeKey(start)
        reverse = not back

        #c_fid = None if (landing or appchange) else request.getCookie("fid")
        folderId = utils.getRequestArg(request, "fid") or None
        #if folderId != c_fid :
        #    request.addCookie('fid', folderId, path="/ajax/messages")

        yield self._checkStandardFolders(request, myKey)
        folders = yield self._getFolders(myKey)
        if folderId is None:
            #Find the Inbox of this user and set it.
            folderId = self._getSpecialFolder(myKey, folders)
        else:
            # Make sure user has access to the folder
            res = yield self._checkUserFolderACL(myKey, folderId)
            if not res:
                raise

        args["folders"] = folders
        args.update({"fid":folderId})

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        res = yield Db.get_slice(key=folderId, column_family="mFolderMessages",
                                 start=start, count=11+int(back), reverse=reverse)

        if back and len(res) < 12:
            # less than 10 messages it first pages, not good UX
            # fetch messages as if start is not given.
            back = False
            start = ''
            res = yield Db.get_slice(key=folderId,
                                     column_family="mFolderMessages",
                                     count=11, reverse=True)
        # Fetch the message-ids from mFolderMessages
        mids = utils.columnsToDict(res, ordered=True).values()
        tids = utils.columnsToDict(res, ordered=True).keys()
        tids = [utils.encodeKey(x) for x in tids]

        #The start key will help us go back and end key to go forward in paging
        if not back:
            startKey = tids[0] if len(tids) and start else 0
            endKey = 0 if len(tids) == 0 or len(mids) < 11 else tids[-1]
            mids = mids[:-1] if len(mids) == 11 else mids

        else:
            mids.reverse()
            tids.reverse()
            startKey = 0 if len(tids) < 12 else tids[1]
            endKey =  tids[-1] if len(tids) > 0 else 0
            mids = mids[:-1]
            if len(mids) == 11:
                mids.pop(0)
        args.update({"start":startKey, "end":endKey})
        # Count the total number of messages in this folder
        #XXX: We don't really need to show the total number of messages at the
        # moment.
        #args.update({"total":res})
        yield self._updateFolderStats(myKey, folderId)


        if len(mids) > 0:
            res = yield Db.get_slice(key=myKey, column_family="mUserMessages",
                                          names=mids)
            messageFlags = utils.supercolumnsToDict(res)
        else:
            messageFlags = {}

        res = yield Db.multiget_slice(keys=mids, column_family="messages")
        msgs = utils.multiColumnsToDict(res, ordered=True)
        for mid, msg in msgs.iteritems():
            people, myself = yield self._generatePeopleInConversation(msg, myKey)
            msg.update({"people":people, "tid": tids[mids.index(mid)]})
            msg.update({"myself":myself})
            msg.update({"flags":messageFlags[mid]})
        args.update({"messages":msgs})
        args.update({"mids":mids})
        args.update({"view":"messages"})

        if script:
            onload = """
                     $('#sfmenu').children().each(function(index) {
                         $(this).removeClass('sidemenu-selected')
                     });
                     $('#ufmenu').children().each(function(index) {
                         $(this).removeClass('sidemenu-selected')
                     });
                     $('li#%s').addClass('sidemenu-selected');
                     $('#mainbar .contents').removeClass("has-right");
                     """ % folderId
            yield renderScriptBlock(request, "message.mako", "center",
                                    landing, ".center-contents", "set", True,
                                    handlers={"onload": onload},
                                    **args)
        else:
            yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderThread(self, request):
        #Based on the request, render a message or a conversation
        thread = request.args.get("id", [None])[0]
        folderId = request.args.get("fid", [None])[0]
        #XXXBased on the user's preference, the id can be a message id or a
        # conversation id. In a conversation view, a single message can only be
        # viewed in the context of the entire conversation it belongs to. If
        # both conversation and message id are mentioned: the conversation will
        # be displayed and the message; if it belongs to the conversation will
        # be expanded.

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        landing = not self._ajax
        conversationView = False

        folders = yield self._getFolders(myKey)
        if folderId is None:
            #Find the Inbox of this user and set it.
            for fId, fInfo in folders.iteritems():
                if ("special" in fInfo) and (fInfo["special"] == "INBOX"):
                    folderId = fId
                    break
        else:
            # Make sure user has access to the folder
            res = yield self._checkUserFolderACL(myKey, folderId)
            if not res:
                raise

        args["folders"] = folders
        args.update({"fid":folderId})

        if script and landing:
            yield render(request, "message.mako", **args)

        if appchange and script:
            yield renderScriptBlock(request, "message.mako", "layout",
                                    landing, "#mainbar", "set", **args)

        if thread:
            #XXX: the viewer needs to have the necessary acls to view this
            hasAccess = yield self._checkUserHasMessageAccess(myKey, thread)
            if not hasAccess:
                raise Unauthorized

            res = yield Db.get_slice(key=thread, column_family="messages")
            msgs = utils.columnsToDict(res)
            if len(msgs) > 0:
                #Mark the message as read.XXX: This will change when
                #   conversations are implemented
                yield self._setFlagOnMessage(myKey, thread, "read", "1")
                yield self._setFlagOnMessage(myKey, thread, "new", "0")
                #TODO: Update the flag stats for this folder
                res = yield Db.get_slice(key=myKey,
                                         column_family="mUserMessages",
                                         names=[thread])
                flags = utils.supercolumnsToDict(res)[thread]
                people, myself = yield self._generatePeopleInConversation(msgs, myKey)
                msgs.update({"people":people})
                msgs.update({"myself":myself})
                args.update({"message":msgs})
                args.update({"id":thread})
                args.update({"flags":flags})
                args.update({"view":"message"})
                if script:
                    yield renderScriptBlock(request, "message.mako", "right",
                                            landing, ".right-contents", "set", **args)

                    yield renderScriptBlock(request, "message.mako", "center",
                                            landing, ".center-contents", "set", **args)
                else:
                    yield render(request, "message.mako", **args)
            else:
                request.redirect("/messages?fid=%s"%(folderId))
        else:
            request.redirect("/messages?fid=%s"%(folderId))

    @defer.inlineCallbacks
    def _deliverMessage(self, request, message, recipients):
        #Deliver the message to the sender's collection
        myKey = auth.getMyKey(request)
        flags = {"read":"1"}
        folders = yield self._getFolders(myKey)
        sentFolderId = self._getSpecialFolder(myKey, folders, "SENT")

        yield self._checkStandardFolders(request, myKey)
        yield self._deliverToUser(myKey, sentFolderId, message, flags)

        for recipient in recipients:
            #Deliver  to each recipient's Inbox
            #Check if the recipient has the standard folders
            yield self._checkStandardFolders(request, recipient)
            folders = yield self._getFolders(recipient)
            inboxFolderId = self._getSpecialFolder(recipient, folders, "INBOX")
            yield self._deliverToUser(recipient, inboxFolderId, message, None)

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
        timestamp = message["timestamp"]

        messageInfo = {}
        messageInfo["conversation"] = conversationId
        messageInfo["read"] = flags.get("read", "0")
        messageInfo["star"] = flags.get("star", "0")
        messageInfo["new"] = flags.get("new", "1")
        messageInfo["timestamp"] = timestamp

        yield Db.batch_insert(userId, "mUserMessages", {messageId: messageInfo})

        #Insert the new message to the folders cf
        yield Db.insert(folderId, "mFolderMessages", messageId, timestamp)

        #Update the folder into which the message was created in mInFolders cf
        yield Db.insert(messageId, "mInFolders", "", folderId)

        #Insert this message into a new conversation
        yield Db.insert(conversationId, "mConversationMessages",
                        messageId, timestamp)

        #Update the total count for this folder
        yield self._updateFolderStats(userId, folderId)

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
            name, mailId = parseaddr(recipient)
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
        #Since we will deal with composer related forms. Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        body = utils.getRequestArg(request, "body")
        body = body.decode('utf-8').encode('utf-8', "replace")
        parent = utils.getRequestArg(request, "parent") #TODO
        subject = utils.getRequestArg(request, "subject") or None
        if subject: subject.decode('utf-8').encode('utf-8', "replace")
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
        people = re.sub(',\s+', ',', sender+","+to+cc+shared).split(",")
        people_ids = []
        for p in people:
            rtuple = parseaddr(p)
            remail = rtuple[1]
            people_ids.append(remail)

        res = yield Db.multiget_slice(people_ids, "userAuth", ["user"])
        res = utils.multiColumnsToDict(res)
        people_map = {}
        for p in res.keys():
            people_map[p] = res[p]['user']
        uid_people = {}
        for p in res.keys():
            uid_people[res[p]['user']] = p
        uids = uid_people.keys()
        res = yield Db.multiget_slice(uids, 'entities', ["basic"])
        res = utils.multiSuperColumnsToDict(res)
        people, myself = {}, ""
        for uid in res.keys():
            pemail = uid_people[uid]
            people[pemail] = res[uid]
            people[pemail]["uid"] = uid
            if uid == myKey:
                myself = pemail
        defer.returnValue((people, myself))

    @defer.inlineCallbacks
    def _checkStandardFolders(self, request, userId):
        #Standard folders have the same key as their labels.
        res = yield Db.get_count(key=userId, column_family='mUserFolders')
        if res == 0:
            for sf in self._specialFolders:
                yield self._createFolder(request, userId, _(sf.title()), sf)
        else:
            defer.returnValue(1)

    @defer.inlineCallbacks
    def _createFolder(self, request, userId, folderName, specialName=None):
        acl = {'accept':{}}
        folderItem = utils.createNewItem(request, "folder", userId, acl)
        folderId = utils.getUniqueKey()
        folderItem["props"] = {"label":folderName}
        if specialName:
            folderItem["props"]["special"] = specialName
        userFolderItem = {"total":"0", "unread":"0", "new":"0", "nested":"0", "subscribed":"1"}
        yield Db.batch_insert(folderId, "mFolders", mapping=folderItem)
        yield Db.batch_insert(userId, "mUserFolders", {folderId:userFolderItem})

    @defer.inlineCallbacks
    def _getFolders(self, userId, subscribed=True):
        #Return a list of folders belonging to a user. Later we will have
        #   folders shared with him and public folders. Similar to namespaces
        #   in IMAP4
        folders = {}
        res = yield Db.get_slice(userId, "mUserFolders")
        userInfo = utils.supercolumnsToDict(res)
        fIds = userInfo.keys()
        res = yield Db.multiget_slice(fIds, "mFolders", ["props"])
        folderInfo = utils.multiSuperColumnsToDict(res)
        for fId in fIds:
            folders[fId] = dict(userInfo[fId], **folderInfo[fId]["props"])
        defer.returnValue(folders)

    def _getSpecialFolder(self, userId, folders, folderType="INBOX"):
        folderId = ""
        for fId, fInfo in folders.iteritems():
            if ("special" in fInfo) and (fInfo["special"] == folderType):
                folderId = fId
                break
        return folderId

    @defer.inlineCallbacks
    def _updateFolderStats(self, userId, folderId):
        #Update the total, unread and new messages stats for a folder
        #TODO: Update the flag stats for this folders
        res = yield Db.get_count(folderId, "mFolderMessages")
        newFolderStats = {'total':str(res)}
        yield Db.batch_insert(userId, "mUserFolders",
                              mapping={folderId:newFolderStats})


    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None

        if segmentCount == 0:
            d = self._renderMessages(request)
        elif segmentCount == 1 and request.postpath[0] == "write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0] == "thread":
            d = self._renderThread(request)
        elif segmentCount == 1 and request.postpath[0] == "actions":
            d = self._threadActions(request)

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
