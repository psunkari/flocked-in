
import os
import ConfigParser
import gettext
from ordereddict        import OrderedDict

from telephus.pool      import CassandraClusterPool
from twisted.internet   import reactor
from twisted.plugin     import getPlugins

from social.isocial     import IItemType


# Read configuration
config_sources = os.environ.get("CONFIG_SOURCES", "etc/social.cfg").split(",")
Config = ConfigParser.ConfigParser()
Config.read([os.path.abspath(source) for source in config_sources])


# Cassandra connection pool
cassandraNodes = Config.get("Cassandra", "Nodes").split(',\s*')
cassandraKeyspace = Config.get("Cassandra", "Keyspace")
Db = CassandraClusterPool(cassandraNodes, cassandraKeyspace, pool_size=10)
Db.startService()


# Aliases for i18n
_ = gettext.gettext
__ = gettext.ngettext


# Map of all item type plugins
plugins = {}
for plg in getPlugins(IItemType):
    if not hasattr(plg, "disabled") or not plg.disabled:
        plugins[plg.itemType] = plg


whitelist = []
blacklist = []
try:
    wlist = open('etc/whitelist.txt', 'r').readlines()
    whitelist = [domain.strip() for domain in wlist if domain]
except IOError:
    pass

try:
    blist = open('etc/blacklist.txt', 'r').readlines()
    blacklist = [domain.strip() for domain in blist if domain]
except IOError:
    pass

__all__ = [Config, Db, _, __, plugins, whitelist, blacklist]
