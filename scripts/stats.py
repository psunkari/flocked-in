#!/usr/bin/python
"""


"""
import os
import sys
import optparse
import time
import datetime
import pprint

from twisted.internet import defer, reactor
from twisted.python import log

sys.path.append(os.getcwd())
from social import config, db, utils
from social.template import getBlock



KEYSPACE = config.get("Cassandra", "Keyspace")
dateFormat = '%Y-%m-%d'


@defer.inlineCallbacks
def getNewUserCount(startDate, endDate, count=100, column_count = 100, mail_to = ''):

    frm_to = startDate + ' ' + endDate
    startDate = datetime.datetime.strptime(startDate, dateFormat)
    endDate = datetime.datetime.strptime(endDate, dateFormat)
    if endDate <= startDate:
        log.msg("end-date should be later than start-date")
        raise Exception("end-date should be later than start-date")

    startTime = time.mktime(startDate.timetuple())
    endTime = time.mktime(endDate.timetuple())

    toFetchCount = count +1
    toFetchColumnCount = column_count +1
    new_domains = []
    start = ''
    stats = {}
    data = {}


    while 1:
        domains = yield db.get_range_slice('domainOrgMap',
                                            count=toFetchCount,
                                            start=start)

        for row in domains[:count]:
            domain = row.key
            for col in row.columns[:count]:
                if domain not in data.setdefault(col.column.name, {}).setdefault("domain", []):
                    data[col.column.name]["domain"].append(domain)
                column_timestamp = col.column.timestamp/1000000.0
                if column_timestamp < endTime and column_timestamp >= startTime:
                    if domain not in new_domains:
                        new_domains.append(domain)

        if len(domains) < toFetchCount:
            break
        else:
            start = domains[-1].key
    stats = {frm_to: {"newDomains":new_domains, "newDomainCount": len(new_domains) }}



    start =  ''
    new_users = {}
    usersOrgMap = {}
    totalNewUsers = 0
    while 1:
        users = yield db.get_range_slice('orgUsers',
                                        start=start,
                                        count=toFetchCount,
                                        column_count=toFetchColumnCount)
        for row in users[:count]:
            orgId = row.key
            for col in row.columns[:column_count]:
                userId  = col.column.name
                usersOrgMap[userId] = orgId
                if userId not in data.setdefault(orgId, {}).setdefault("users", {}):
                    data[orgId]['users'][userId] = {"newItems":0, "items":0}
                column_timestamp = col.column.timestamp/1000000.0
                if column_timestamp < endTime and column_timestamp >= startTime:
                    if col.column.name not in new_users.setdefault(orgId, []):
                        new_users[orgId].append(userId)
            if len(row.columns) == toFetchColumnCount:
                column_start = row.columns[-1].column.name
                while 1:
                    _users = yield db.get_range_slice('orgUsers',
                                                      count=1,
                                                      start=orgId,
                                                      column_start=column_start,
                                                      column_count=toFetchColumnCount)
                    for col in _users[0].columns[:column_count]:
                        userId = col.column.name
                        usersOrgMap[userId] = orgId
                        if userId not in data.setdefault(orgId, {}).setdefault("users", {}):
                            data[orgId]['users'][userId] = {'newItems':0, 'items':0}
                        column_timestamp = col.column.timestamp/1000000.0
                        if column_timestamp < endTime and column_timestamp >= startTime:
                            if col.column.name not in new_users[orgId]:
                                new_users[orgId].append(userId)
                    if len(_users[0].columns) == toFetchColumnCount:
                        column_start = _users[0].columns[-1].column.name
                    else:
                        break
            totalNewUsers += len(new_users.get(orgId, []))
        if len(users) < toFetchCount:
            break
        else:
            start = users[-1].key

    stats[frm_to]["signups"] = totalNewUsers


    start = ''
    while 1:
        rows = yield db.get_range_slice('userItems',
                                        start=start,
                                        count=toFetchCount,
                                        column_count = toFetchColumnCount)
        for row in rows[:count]:
            userId = row.key
            for col in row.columns[:column_count]:

                if userId not in usersOrgMap:
                    data['no-org'] = {"users":{userId:{"items": 0, "newItems": 0}}}
                    orgId = 'no-org'
                else:
                    orgId = usersOrgMap[userId]
                if userId not in data[orgId]['users'] :
                    data[orgId]['users'] = {'items': 0 , 'newItems': 0}
                column_timestamp = col.column.timestamp/1000000.0
                if column_timestamp < endTime and column_timestamp >= startTime:
                    data[orgId]['users'][userId]['newItems'] += 1
                data[orgId]['users'][userId]['items'] += 1
            if len(row.columns) == toFetchColumnCount:
                cstart = row.columns[-1].column.name
                while 1:
                    userItems = yield db.get_range_slice('userItems', count=1,
                                                        start=userId,
                                                        column_start= cstart,
                                                        column_count= toFetchColumnCount)
                    for col in userItems[0].columns[:column_count]:
                        column_timestamp = col.column.timestamp/1000000.0
                        if column_timestamp < endTime and column_timestamp >= startTime:
                            data[orgId]['users'][userId]['newItems'] += 1
                        #if userId in data[orgId]['users'] :
                        data[orgId]['users'][userId]['items'] += 1
                    if len(userItems[0].columns) == toFetchColumnCount:
                        cstart = userItems[0].columns[-1].column.name
                    else:
                        break

        if len(rows) < toFetchCount:
            break
        else:
            start = rows[-1].key

    stats["domain"] = {}
    for orgId in data:
        domainName = ",".join(data[orgId]['domain'])
        stats["domain"][domainName] = {}
        stats["domain"][domainName]["newUsers"] = len(new_users.get(orgId, []))
        stats["domain"][domainName]["totalUsers"] = len(data[orgId].get('users', {}).keys())
        stats["domain"][domainName]["newItems"] = sum([data[orgId]['users'][x]['newItems'] for x in data[orgId].get('users', {})])
        stats["domain"][domainName]["items"] =    sum([data[orgId]['users'][x]['items'] for x in data[orgId].get('users', {})])

    if not mail_to:
        print pprint.pprint(stats)
    subject = "Stats: %s to %s" % (startDate.strftime(dateFormat), endDate.strftime(dateFormat))
    textPart = repr(stats)
    rootUrl = config.get('General', 'URL')
    brandName = config.get('Branding', 'Name')
    htmlPart = getBlock("emails.mako", "html_stats",  **{"stats":stats, "frm_to": frm_to, 'rootUrl': rootUrl, 'brandName': brandName})
    for mailId in mail_to:
        yield utils.sendmail(mailId, subject, textPart, htmlPart)



def main():

    today = datetime.datetime.now().date()
    yesterday = today - datetime.timedelta(days=1)

    parser = optparse.OptionParser()
    parser.add_option("--start-date",
                        dest = 'start_date',
                        action="store",
                        default= yesterday.strftime(dateFormat))
    parser.add_option('--end-date',
                        dest="end_date",
                        action="store",
                        default=today.strftime(dateFormat))
    parser.add_option('--row-count',
                        dest="row_count",
                        action="store",
                        type="int",
                        default=100)
    parser.add_option('--column-count',
                        dest='column_count',
                        action='store',
                        type='int',
                        default=100)
    parser.add_option('--send-mail',
                        dest='send_mail',
                        action='store_true')
    parser.add_option('--mail-to',
                        dest='mail_to',
                        action='store',
                        default='sivakrishna@synovel.com,praveen@synovel.com')
    options, args = parser.parse_args()

    log.startLogging(sys.stdout)
    db.startService()
    mail_to = []
    if options.send_mail:
        mail_to = [x.strip() for x in options.mail_to.split(',')]
    d = getNewUserCount(options.start_date, options.end_date,
                        options.row_count, options.column_count, mail_to)

    def finish(x):
        db.stopService()
        reactor.stop()
    d.addErrback(log.err)
    d.addBoth(finish)
    reactor.run()






if __name__ == '__main__':

    main()
