
from twisted.application import internet, service
from twisted.web import server
from twisted.cred.portal import Portal

from social.service import Service
from social.auth import AuthWrapper, AuthRealm
from social.auth import UserPasswordChecker, UserSessionChecker, AuthTokenChecker
from social import Config

root = Service().root()

checkers = [UserSessionChecker(), UserPasswordChecker(), AuthTokenChecker()]
wrapper = AuthWrapper(Portal(AuthRealm(root), checkers))

application = service.Application('social')
collection = service.IServiceCollection(application)

listen = int(Config.get('General', 'ListenPort'))
internet.TCPServer(listen, server.Site(wrapper)).setServiceParent(collection)
