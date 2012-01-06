import pytz
import os
import ConfigParser
import gettext
from ordereddict        import OrderedDict

from telephus.pool      import CassandraClusterPool
from telephus.cassandra.ttypes import ConsistencyLevel
from twisted.internet   import reactor
from twisted.plugin     import getPlugins

from social.isocial     import IItemType


#
# Read configuration + cache a few values
#
config = ConfigParser.ConfigParser()
with open('etc/defaults.cfg') as defaults:
    config.readfp(defaults)
config.read(['etc/devel.cfg','etc/production.cfg'])
cdnHost = config.get("General", "CDNHost")
secureProxy = config.get("General", "SecureProxy")
rootUrl = config.get("General", "URL")


#
# Cassandra connection pool
#
cassandraNodes = config.get("Cassandra", "Nodes").split(',')
cassandraKeyspace = config.get("Cassandra", "Keyspace")
db = CassandraClusterPool(cassandraNodes, cassandraKeyspace, pool_size=10)
db.set_consistency(ConsistencyLevel.LOCAL_QUORUM)


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
    whitelist = set([domain.strip() for domain in wlist if domain.strip()])
except IOError:
    pass

try:
    blist = open('etc/blacklist.txt', 'r').readlines()
    blacklist = set([domain.strip() for domain in blist if domain.strip()])
except IOError:
    pass

tmp = {}
for countryId in pytz.country_names:
    try:
        a = pytz.country_timezones(countryId)
        if len(a) == 1:
            tmp[pytz.country_names[countryId]] = a[0]
        else:
            for zone in a:
                city = zone.split('/')[-1].replace('_', ' ')
                tmp['%s - %s '%(pytz.country_names[countryId], city)] = zone
    except:
        pass
location_tz_map =  OrderedDict()
location_tz_map['Hawaii'] = 'US/Hawaii'
location_tz_map['Alaska'] = 'US/Alaska'
location_tz_map['Arizona'] = 'US/Arizona'
location_tz_map['Pacific Time - (US & Canada)'] = 'US/Pacific'
location_tz_map['Mountain Time - (US & Canada)'] = 'US/Mountain'
location_tz_map['Central Time - (US & Canada)'] = 'US/Central'
location_tz_map['Eastern Time - (US & Canada)'] = 'US/Eastern'

countries = tmp.keys()
countries.sort()
for countryId in countries:
    location_tz_map[countryId] = tmp[countryId]


__all__ = [config, db, plugins, whitelist, location_tz_map,
           blacklist, cdnHost, secureProxy, _, __]
