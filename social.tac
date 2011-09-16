
from twisted.application    import internet, service
from twisted.python.logfile import DailyLogFile
from twisted.python.log     import ILogObserver

from social                 import config, db
from social.logging         import logObserver
from social.root            import RootResource
from social.server          import SiteFactory, RequestFactory, SessionFactory

root = RootResource()
application = service.Application('social')
logfile = DailyLogFile("flockedin.log", "/tmp")
application.setComponent(ILogObserver, logObserver(logfile).emit)
db.setServiceParent(application)

factory = SiteFactory(root)
factory.sessionFactory = SessionFactory
factory.requestFactory = RequestFactory
factory.displayTracebacks = False

listen = int(config.get('General', 'ListenPort'))
internet.TCPServer(listen, factory).setServiceParent(application)
