
import os
import ConfigParser
import gettext

from telephus.protocol  import ManagedCassandraClientFactory
from telephus.client    import CassandraClient
from twisted.internet   import reactor


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

__all__ = [Config, Db, _, __]
