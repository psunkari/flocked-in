
import os
import ConfigParser
import gettext
from ordereddict        import OrderedDict

from telephus.pool      import CassandraClusterPool
from twisted.internet   import reactor
from twisted.plugin     import getPlugins

from social.isocial     import IItemType


#
# Read configuration
#
config_sources = os.environ.get("CONFIG_SOURCES", "etc/production.cfg").split(",")
config = ConfigParser.ConfigParser()
config.read([os.path.abspath(source) for source in config_sources])


#
# Cassandra connection pool
#
cassandraNodes = config.get("Cassandra", "Nodes").split(',')
cassandraKeyspace = config.get("Cassandra", "Keyspace")
db = CassandraClusterPool(cassandraNodes, cassandraKeyspace, pool_size=10)


#
# Internationalization
# Aliases for i18n
#
_ = gettext.gettext
__ = gettext.ngettext


#
# Map of all item type plugins
#
plugins = {}
for plg in getPlugins(IItemType):
    if not hasattr(plg, "disabled") or not plg.disabled:
        plugins[plg.itemType] = plg


#
# Whitelist: List of domains that can invite anyone to flocked.in
# Blacklist: List of domains that cannot create networks on flocked.in
#
whitelist = []
blacklist = []
try:
    wlist = open('etc/whitelist.txt', 'r').readlines()
    whitelist = set([domain.strip() for domain in wlist if domain])
except IOError:
    pass

try:
    blist = open('etc/blacklist.txt', 'r').readlines()
    blacklist = set([domain.strip() for domain in blist if domain])
except IOError:
    pass


__all__ = [config, db, plugins, whitelist, blacklist, _, __]
