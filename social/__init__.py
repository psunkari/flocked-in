
import os
import ConfigParser
import gettext
from ordereddict        import OrderedDict

from telephus.protocol  import ManagedCassandraClientFactory
from telephus.client    import CassandraClient
from twisted.internet   import reactor
from twisted.plugin     import getPlugins

from social.isocial     import IItem

Config = ConfigParser.ConfigParser()
Config.read([os.path.abspath('etc/social.cfg')])


_dbhost = Config.get("Cassandra", "Host")
_dbport = Config.get("Cassandra", "Port")
_keyspace = Config.get("Cassandra", "Keyspace")
_factory = ManagedCassandraClientFactory(_keyspace)
reactor.connectTCP(_dbhost, int(_dbport), _factory)
Db = CassandraClient(_factory)

_ = gettext.gettext
__ = gettext.ngettext

_positionMap = {}
_positions = []
for plugin in getPlugins(IItem):
    _positions.append(plugin.position)
    _positionMap[plugin.position] = plugin

_positions.sort()
plugins = OrderedDict()
for position in _positions:
    plugin = _positionMap[position]
    plugins[plugin.itemType] = plugin


__all__ = [Config, Db, _, __, plugins]
