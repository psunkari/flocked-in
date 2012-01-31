
from twisted.application    import internet, service
from twisted.python.logfile import DailyLogFile
from twisted.python.log     import ILogObserver
from twisted.scripts        import twistd
from twisted.internet       import reactor

from social                 import config, db
from social.comet           import comet
from social.logging         import logObserver
from social.root            import RootResource
from social.server          import SiteFactory, RequestFactory, SessionFactory

root = RootResource()
options = twistd.ServerOptions()
application = service.Application('social')

# We try to parse to options passed to twistd to determine
# if we should start logging to stdout
try:
    options.parseOptions()
except usage.error, ue:
    print config
    print "%s: %s" % (sys.argv[0], ue)
else:
    # Log to files only if daemonized.
    if not options.get("nodaemon", False):
        logdir = config.get('General', 'LogPath')
        logfile = DailyLogFile("social.log", logdir)
        application.setComponent(ILogObserver, logObserver(logfile).emit)

    # Let the database connections start/stop with the application
    db.setServiceParent(application)

    # Custom session and request factories
    factory = SiteFactory(root)
    factory.sessionFactory = SessionFactory
    factory.requestFactory = RequestFactory
    factory.displayTracebacks = False

    # Finally, start listening!
    listen = int(config.get('General', 'ListenPort'))
    internet.TCPServer(listen, factory).setServiceParent(application)
    reactor.addSystemEventTrigger("before", "shutdown", comet.disconnect)
