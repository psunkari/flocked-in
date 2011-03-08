
import os
import ConfigParser
import gettext
from ordereddict        import OrderedDict

from telephus.protocol  import ManagedCassandraClientFactory
from telephus.client    import CassandraClient
from twisted.internet   import reactor
from twisted.plugin import getPlugins

from social.isocial     import IItem


# Read configuration
Config = ConfigParser.ConfigParser()
Config.read([os.path.abspath('etc/social.cfg')])


# Connect to Cassandra
_dbhost = Config.get("Cassandra", "Host")
_dbport = Config.get("Cassandra", "Port")
_keyspace = Config.get("Cassandra", "Keyspace")
_factory = ManagedCassandraClientFactory(_keyspace)
reactor.connectTCP(_dbhost, int(_dbport), _factory)
Db = CassandraClient(_factory)


# Aliases for i18n
_ = gettext.gettext
__ = gettext.ngettext


# Map of all item type plugins
_pluginList = sorted([x for x in getPlugins(IItem)], key=lambda x: x.position)
plugins = {}
for plg in _pluginList:
    plugins[plg.itemType] = plg
    

__all__ = [Config, Db, _, __, plugins]
