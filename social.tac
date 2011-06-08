
from twisted.application    import internet, service

from social                 import Config
from social.root            import RootResource
from social.server          import SiteFactory, RequestFactory, SessionFactory

root = RootResource()

application = service.Application('social')

factory = SiteFactory(root)
factory.sessionFactory = SessionFactory
factory.requestFactory = RequestFactory
factory.displayTracebacks = False

listen = int(Config.get('General', 'ListenPort'))
internet.TCPServer(listen, factory).setServiceParent(application)
