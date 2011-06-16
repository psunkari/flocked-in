
from twisted.application    import internet, service

from social                 import config, db
from social.root            import RootResource
from social.server          import SiteFactory, RequestFactory, SessionFactory


root = RootResource()
application = service.Application('social')
db.setServiceParent(application)

factory = SiteFactory(root)
factory.sessionFactory = SessionFactory
factory.requestFactory = RequestFactory
factory.displayTracebacks = False

listen = int(config.get('General', 'ListenPort'))
internet.TCPServer(listen, factory).setServiceParent(application)
