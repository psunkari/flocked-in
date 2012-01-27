#!/usr/bin/python

import sys
import json
import uuid
import urllib
import traceback

from zope.interface             import implements
from twisted.python             import log
from twisted.internet           import defer, reactor, protocol
from twisted.web                import client
from twisted.web.iweb           import IBodyProducer
from twisted.internet           import defer
from twisted.web.client         import Agent
from twisted.web.http_headers   import Headers

from social                     import config


COMET_URL=config.get('Cometd', 'url')
SECRET=config.get('Cometd', 'secret')
class _StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class _ResponseReceiver(protocol.Protocol):
    def __init__(self, response, d):
        self.buf = ''
        self.d = d
        self.response = response

    def dataReceived(self, data):
        self.buf += data

    def connectionLost(self, reason):
        # TODO: test if reason is twisted.web.client.ResponseDone, if not, do an errback
        self.d.callback((self.response, self.buf))


class CometdClient:
    def __init__(self, url, secret):
        self.baseUrl = url
        self.clientId = None
        self.initialized = False
        self.connected = False

        self._msgId = 0
        self._backlog = []
        self._handlers = {}
        self._connectionType = "long-polling"
        self._supportedVersion = 1.0
        self._cookies = {'session': secret}

    def _request(self, message, headers=None, method='POST'):
        agent = Agent(reactor)
        data = json.dumps(message)
        headers = {} if not headers else headers
        headers.update({'Content-Type': ['application/json'],
                        'Cookie': ['; '.join(["%s=%s"%(x,y) for x,y in self._cookies.items()])]})
        d = agent.request(method, self.baseUrl, Headers(headers),
                          _StringProducer(data))

        def gotResponse(response):
            if response.code == 204:
                d = defer.succeed('')
            else:
                d = defer.Deferred()
                response.deliverBody(_ResponseReceiver(response, d))
            return d
        d.addCallback(gotResponse)
        return d

    def _createBayeuxMessage(self):
        self._msgId += 1
        message = {"id": self._msgId}
        if self.clientId:
            message["clientId"] = self.clientId
        return message

    @defer.inlineCallbacks
    def handshake(self):
        message = self._createBayeuxMessage()
        message.update({"channel": "/meta/handshake",
                        "supportedConnectionTypes": [self._connectionType],
                        "minimumVersion": 0.9,
                        "version": self._supportedVersion,
                        "advice":{"interval":0,"timeout":60000}})
        (response, body) = yield self._request(message)
        cookies = response.headers.getRawHeaders('Set-Cookie', None)
        for cookie in cookies:
            (name, value) = cookie.split(';')[0].split('=')
            self._cookies[name] = value

        body = json.loads(body)
        for message in body:
            if message.get('channel', None) == "/meta/handshake":
                if not message.get('successful', False):
                    raise Exception(message.get('error'), message)
                self.clientId = message.get('clientId', None)


    def startup(self, ):
        """
        Start long polling requests to POST to /social/cometd/connect
        Until the user is disconnected.
        Will need clientId, request id and BAYEUX_BROWSER
        """

    def disconnect(self, ):
        """
        Publish to [/meta/disconnect] channel to disconnect from the server
        Will need clientId, request id and BAYEUX_BROWSER
        """

    @defer.inlineCallbacks
    def publish(self, channel, data):
        message = self._createBayeuxMessage()
        message.update({"channel": channel,
                        "data": data})

        (request, body) = yield self._request(message)
        body = json.loads(body)
        for message in body:
            if message.get('channel', None) == channel:
                if not message.get('successful', False):
                    raise Exception(message.get('error'), message)

    def subscribe(self, ):
        """
        TODO: Will be implemented in future.
        """

    def unsubscribe(self, ):
        """
        TODO: Will be implemented in future.
        """


@defer.inlineCallbacks
def startup():
    comet = CometdClient(COMET_URL, SECRET)
    try:
        yield comet.handshake()
        yield comet.publish('/hello', {'greeting': 'Hello, World!'})
    except Exception as ex:
        log.err(ex)

cometdClient = CometdClient(COMET_URL, SECRET)

@defer.inlineCallbacks
def pushToCometd(channelId, data):
    yield cometdClient.handshake()
    yield cometdClient.publish(channelId, data)


if __name__ == "__main__":
    d = startup()
    d.addBoth(lambda x: reactor.stop())
    reactor.run()
