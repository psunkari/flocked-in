#!/usr/bin/python

import time
import sys
import json
import uuid
import urllib
import traceback
import httplib
from    urlparse                import urljoin, urlparse

from zope.interface             import implements
from twisted.python             import log
from twisted.internet           import defer, reactor, protocol, threads, task
from twisted.web                import client
from twisted.web.iweb           import IBodyProducer
from twisted.internet           import defer
from twisted.web.client         import Agent
from twisted.web.http_headers   import Headers

from social                     import config

COMET_BASEURL = config.get('Cometd', 'BaseUrl')
COMET_PATH = config.get('Cometd', 'Path')
COMET_SECRET=config.get('Cometd', 'secret')

class CometRetryException(Exception):
    """
    """

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
    def __init__(self, url, path, secret):
        self.baseUrl = url
        self.path = path
        self.clientId = None
        self.initialized = False
        self.connected = False

        self._msgId = 0
        self._backlog = []
        self._handlers = {}
        self._connectionType = "long-polling"
        self._supportedVersion = 1.0
        self._cookies = {'session': secret}
        self.url = urljoin("http://"+self.baseUrl, path)

    def _request(self, message, headers=None, method='POST'):
        agent = Agent(reactor)
        data = json.dumps(message)
        headers = {} if not headers else headers

        headers.update({'Content-Type': ['application/json'],
                        'Cookie': ['; '.join(["%s=%s"%(x,y) for x,y in self._cookies.items()])]})
        d = agent.request(method, self.url, Headers(headers),
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

    def _createBayeuxMessage(self, idPrefix=''):
        self._msgId += 1
        message = {"id": idPrefix+str(self._msgId)}
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
        if response.code != 200:
            raise Exception('handshake failed')
        cookies = response.headers.getRawHeaders('Set-Cookie', [])
        for cookie in cookies:
            (name, value) = cookie.split(';')[0].split('=')
            self._cookies[name] = value

        body = json.loads(body)
        for message in body:
            if message.get('channel', None) == "/meta/handshake":
                if not message.get('successful', False):
                    raise Exception(message.get('error'), message)
                self.clientId = message.get('clientId', None)

    def startup(self, timeout=30000):
        if not self.clientId:
            raise errors.InvalidRequest()
        conn = httplib.HTTPConnection(self.baseUrl, timeout=60)
        message = self._createBayeuxMessage()
        messageId = message["id"]
        message.update({"channel": "/meta/connect",
                        "connectionType": self._connectionType,
                        "advice": {"timeout": timeout}})
        headers = {'Content-Type': ['application/json'],
                    'Cookie': ['; '.join(["%s=%s"%(x,y) for x,y in self._cookies.items()])]}
        conn.request('POST', self.path, json.dumps(message), headers )
        response = conn.getresponse()
        if response.status == 200:
            data = response.read()
            body = json.loads(data)
            for _message in body:
                channel = _message.get('channel', None)
                if channel=='/meta/connect' and messageId == _message.get('id', ''):
                    advice = _message.get('advice', None)
                    if advice and advice.get('reconnect', None):
                        raise CometRetryException(_message)
        else:
            self.clientId = None
            raise Exception(response.reason)

    @defer.inlineCallbacks
    def disconnect(self, ):
        """
       Publish to [/meta/disconnect] channel to disconnect from the server
        Will need clientId, request id and BAYEUX_BROWSER
        """
        message = self._createBayeuxMessage()
        message.update({"channel": "/meta/disconnect"})
        (response, body) = yield self._request(message)
        if response.code != 200:
            raise Exception('failed to disconnect')

    @defer.inlineCallbacks
    def publish(self, channel, data):
        message = self._createBayeuxMessage()
        message.update({"channel": channel,
                        "data": data})

        (request, body) = yield self._request(message)
        if request.code !=200:
            raise Exception('publish failed')
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


comet = CometdClient(COMET_BASEURL, COMET_PATH, COMET_SECRET)
@defer.inlineCallbacks
def startup():
    global comet
    conn = httplib.HTTPConnection(COMET_BASEURL, timeout=60)
    @defer.inlineCallbacks
    def _startup(comet, conn):
        timeout = 30000
        while 1:
            try:
                comet.startup(timeout)
            except CometRetryException as e :
                res = e.args[0]
                advice = res['advice']
                timeout = advice['timeout']
                if advice['reconnect'] == 'retry':
                    interval = advice.get('interval', 0)
                    time.sleep(interval/1000)
                elif advice['reconnect'] == 'handshake':
                    #yield comet.handshake()
                    yield threads.blockingCallFromThread(reactor, comet.handshake)
                elif advice['reconnect'] == 'none':
                    return

    try:
        yield comet.handshake()
        yield threads.deferToThread(_startup, comet, conn)
    except Exception as ex:
        log.err(ex)

d = startup()

if __name__ == "__main__":
    d = startup()
    d.addBoth(lambda x: reactor.stop())
    reactor.run()
