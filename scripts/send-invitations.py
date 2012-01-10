import optparse
import sys
import os

from twisted.internet import defer, reactor
from twisted.python import log
sys.path.append(os.getcwd())
from social import people, utils, db

@defer.inlineCallbacks
def sendInvitations(sender):
    cols = yield db.get_slice(sender, "userAuth")
    senderInfo = utils.columnsToDict(cols)
    senderOrgId = senderInfo['org']
    senderId = senderInfo['user']

    cols = yield db.multiget_slice([senderId, senderOrgId], "entities", ['basic'])
    entities = utils.multiSuperColumnsToDict(cols)

    emails = sys.stdin.readlines()
    emails = [x.strip() for x in emails]
    yield people._sendInvitations([], emails, entities[senderId], senderId, entities[senderOrgId])


if __name__ == '__main__':
    parser = optparse.OptionParser()
    parser.add_option('-s', '--sender', dest="sender", action="store")
    options, args = parser.parse_args()

    if options.sender:
        log.startLogging(sys.stdout)
        db.startService()
        d = sendInvitations (options.sender)

        def finish(x):
            db.stopService()
            reactor.stop();
        d.addErrback(log.err)
        d.addBoth(finish)

        reactor.run()



