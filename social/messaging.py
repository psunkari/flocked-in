import uuid
import random, re
import pytz, time, datetime
import email.utils

from twisted.internet   import defer
from twisted.web        import server
from twisted.python     import log

from telephus.cassandra     import ttypes

from social             import Db, utils, base, auth
from social.template    import render, renderScriptBlock
from social.isocial     import IAuthInfo
from social.constants   import PEOPLE_PER_PAGE


class MessagingResource(base.BaseResource):
    isLeaf = True

    @defer.inlineCallbacks
    def _threadActions(self, request):
        defer.returnValue('0')

    @defer.inlineCallbacks
    def _composeMessage(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        myKey = auth.getMyKey(request)
        landing = not self._ajax
        recipients, body, subject, parent = self._parseComposerArgs(request)

        res = yield Db.get_slice(key=myKey, column_family='entities')
        res = utils.supercolumnsToDict(res)
        name = res["basic"]["name"]
        email = res["contact"]["mail"]
        from_header = "%s <%s>" %(name, email)

        new_message_id = str(utils.getUniqueKey()) + "@synovel.com"
        recipient_header, uids = yield self._createRecipientHeader(recipients)
        date_header, epoch = self._createDateHeader()

        if parent:
            #XXX: Check if user has access to this message via acl
            res = yield Db.multiget_slice(keys=[parent], column_family="messages")
            res = utils.multiColumnsToDict(res)
            if parent in res.keys():
                parent = res[parent]
                references = parent["references"] + parent["message-id"]
                irt = parent["message-id"]
                message = {
                          'From': from_header,
                          'To': recipient_header,
                          'Subject': subject,
                          'body':body,
                          'message-id':new_message_id,
                          'Date':date_header,
                          'references':references,
                          'irt':irt,
                          'date_epoch': str(epoch)
                        }
            else:
                #Throw an error
                parent = None
        else:
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
        print "Delivering a new message: " + str(message)
        yield Db.batch_insert(key=new_message_id, column_family = 'messages',
                              mapping = message)
        yield self._deliverMessage(request, message, uids)
        #request.write("$$.fetchUri('/messages/')")

    @defer.inlineCallbacks
    def _renderComposer(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        myKey = auth.getMyKey(request)
        landing = not self._ajax
        parent = request.args.get("parent", [None])[0]

        if parent:
            #XXX: The current user should have the rights to view the message
            #TODO: multiget does not raise an exception!!!. check manually
            try:
                res = yield Db.multiget_slice(keys=[parent], column_family="messages")
            except ttypes.NotFoundException:
                parent_msg = None
            else:
                res = utils.multiColumnsToDict(res)
                if parent in res.keys():
                    parent_msg = res[parent]
                else:
                    parent_msg = None
            finally:
                args.update({"parent_msg":parent_msg})
                args.update({"view":"reply"})
                if script:
                    yield render(request, "message.mako", **args)
        else:
            args.update({"view":"compose"})
            if script:
                yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderMessages(self, request):
        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        myKey = auth.getMyKey(request)
        landing = not self._ajax
        special_folders = ["INBOX", "SENT", "DRAFTS", "TRASH", "ARCHIVES"]
        folder = request.args.get("folder", ["INBOX"])[0]
        if folder.upper() in special_folders:
            folder = folder.upper()
            folder = "%s-%s" %(myKey, folder)

        yield self._checkStandardFolders(myKey)
        try:
            res = yield Db.get(key=myKey, column_family="mUserFolders",
                               super_column=folder, column="label")
            folder_label = res.column.value
            args.update({"folder":folder_label})
        except ttypes.NotFoundException:
            print "whaaa"
            defer.returnValue(0)
        else:
            pass

        res = yield Db.get_slice(key=folder, column_family="mFolderMessages",
                                 count=60)

        #Fetch the message-ids from mFolderMessages
        print "Listing messages in %s" % folder,
        mids = utils.columnsToDict(res, ordered=True).values()
        res = yield Db.multiget_slice(keys=mids, column_family="messages")
        msgs = utils.multiColumnsToDict(res, ordered=True)
        for k,v in msgs.iteritems():
            people = yield self._generatePeopleInConversation(v, myKey)
            v.update({"people":people})
        args.update({"messages":msgs})
        args.update({"mids":mids})
        args.update({"view":"messages"})

        if script:
            yield render(request, "message.mako", **args)

    @defer.inlineCallbacks
    def _renderThread(self, request):
        #Based on the request, render a message or a conversation
        thread=request.args.get("id", [None])[0]
        #XXXBased on the user's preference, the id can be a message id or a
        # conversation id. In a conversation view, a single message can only be
        # viewed in the context of the entire conversation it belongs to. If
        # both conversation and message id are mentioned: the conversation will
        # be displayed and the message; if it belongs to the conversation will
        # be expanded.

        (appchange, script, args, myKey) = yield self._getBasicArgs(request)
        myKey = auth.getMyKey(request)
        landing = not self._ajax
        conversationView = False

        if thread:
            #XXX: the viewer needs to have the necessary acls to view this
            res = yield Db.get_slice(key=thread, column_family="messages")
            msgs = utils.columnsToDict(res)
            if len(msgs) > 0:
                people = yield self._generatePeopleInConversation(msgs, myKey)
                msgs.update({"people":people})
                args.update({"message":msgs})
                args.update({"id":thread})
                args.update({"view":"message"})
                if script:
                    yield render(request, "message.mako", **args)
            else:
                request.write("Message not found")
        else:
            request.write("Message not found")

    @defer.inlineCallbacks
    def _deliverMessage(self, request, message, recipients=None):
        #Deliver the message to the sender's collection
        myKey = auth.getMyKey(request)
        yield self._checkStandardFolders(myKey)
        yield self._deliverToUser(myKey, "%s-%s" %(myKey, "SENT"), message)

        if not recipients:
            recipients = [x[1] for x in [email.utils.parseaddr(message["To"])]]
            res = yield Db.multiget(keys=recipients, column_family="userAuth",
                                    column="user")
            res = utils.multiColumnsToDict(res)
            recipients = [x['user'] for x in res.values() if 'user' in x]

        for recipient in recipients:
            #Deliver  to each recipient's Inbox
            #Check if the recipient has the standard folders
            yield self._checkStandardFolders(recipient)
            yield self._deliverToUser(recipient,
                                      "%s-%s" %(recipient, "INBOX"), message)

    @defer.inlineCallbacks
    def _deliverToUser(self, user_id, folder_id, message):
        if message["irt"] == "":
            isNewMessage = True
        else:isNewMessage = False
        message_id = message["message-id"]
        if isNewMessage:
            conversation_id = utils.getUniqueKey()
        else:
            #XXX:What if the parent is deleted?Do we fetch the references?
            try:
                col = yield Db.get(key=user_id, column_family="mUserMessages",
                                          column="conversation",
                                          super_column=message["irt"])
                print col.column.value
                conversation_id = str(col.column.value)
                print "Found the conversationid: %s" %conversation_id
            except ttypes.NotFoundException:
                conversation_id = utils.getUniqueKey()

        message_id = message["message-id"]
        yield Db.insert(key=user_id, column_family="mUserMessages",
                        value=conversation_id, column="conversation",
                        super_column=message_id)
        yield Db.insert(key=user_id, column_family="mUserMessages",
                        value="0", column="read",
                        super_column=message_id)
        yield Db.insert(key=user_id, column_family="mUserMessages",
                        value="0", column="star",
                        super_column=message_id)

        #TODO:Add the flags to the message, unstarred and read etc.

        #Insert the new message to the folders cf
        yield Db.insert(key=folder_id, column_family="mFolderMessages",
                        column=uuid.uuid1().bytes, value=message_id)

        #Insert this message into a new conversation
        yield Db.insert(key=conversation_id, column_family="mConversationMessages",
                        column=uuid.uuid1().bytes, value=message_id)

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
            rtuple = email.utils.parseaddr(recipient)
            remail = rtuple[1]
            recipients_email.append(remail)

        res = yield Db.multiget_slice(keys=recipients_email, column_family="userAuth")
        res = utils.multiColumnsToDict(res)
        recipient_strings = []
        uids = [x['user'] for x in res.values() if 'user' in x]
        res = yield Db.multiget_slice(keys=uids, column_family='entities')
        res = utils.multiSuperColumnsToDict(res)
        for uid in res.keys():
            recipient_strings.append("%s <%s>" %(res[uid]["basic"]["name"],
                                                 res[uid]["contact"]["mail"]))
        recipient_header = ", ".join(recipient_strings)
        defer.returnValue((recipient_header, uids))

    def _parseComposerArgs(self, request):
        #Since we will deal with composer related forms.Take care of santizing
        # all the input and fill with safe defaults wherever needed.
        #To, CC, Subject, Body,
        recipients = request.args.get("recipients", [''])
        recipients = re.sub(',\s+', ',', recipients[0])
        recipients = recipients.split(",")
        body = request.args.get("body", [""])
        body = body[0]
        subject = request.args.get("subject", ["Private message from XYZ"])[0]
        parent = request.args.get("parent", [None])[0] #TODO
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
            inbox = yield Db.get(key=userid, column_family='mUserFolders',
                                       super_column="%s-%s" %(userid, "INBOX"))
        except ttypes.NotFoundException:
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Inbox", column="label", super_column="%s-%s" %(userid, "INBOX"))
            yield Db.insert(key=userid, column_family='mUserFolders',
                            value="Sent", column="label", super_column="%s-%s" %(userid, "SENT"))

    def render_GET(self, request):
        segmentCount = len(request.postpath)
        d = None
        prematureAbort = False
        if segmentCount == 0:
            request.redirect("/messages/")
            request.finish()
        elif segmentCount == 1 and request.postpath[0]=="":
            d = self._renderMessages(request)
        elif segmentCount == 1 and request.postpath[0]=="write":
            d = self._renderComposer(request)
        elif segmentCount == 1 and request.postpath[0]=="thread":
            d = self._renderThread(request)
        if d:
            def callback(res):
                request.finish()
            def errback(err):
                log.msg(err)
                request.finish()

            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET

    def render_POST(self, request):
        segmentCount = len(request.postpath)
        d = None
        if segmentCount == 0:
            #Handle actions on multiple threads.
            request.finish()
        elif segmentCount == 1 and request.postpath[0]=="write":
            d = self._composeMessage(request)
        elif segmentCount == 1 and request.postpath[0]=="thread":
            #Handle actions on a single thread
            print request.args
            request.finish()
        if d:
            def callback(res):
                request.finish()
            def errback(err):
                log.msg(err)
                request.finish()

            d.addCallbacks(callback, errback)
            return server.NOT_DONE_YET
