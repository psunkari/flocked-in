#!/usr/bin/python

import os
import sys
import optparse
import uuid
import cPickle as pickle
from boto.s3.connection import S3Connection

from telephus.cassandra import ttypes
from twisted.internet   import defer, reactor
from twisted.internet   import threads
from twisted.python     import log

sys.path.append(os.getcwd())
from social import config, db, utils


KEYSPACE = config.get("Cassandra", "Keyspace")

def _getAllFiles(conn, bucket):
    bucket = conn.get_bucket(bucket)
    files = []
    for key in bucket.list():
        files.append(key.name)

    return files

@defer.inlineCallbacks
def updateData():
    SKey = config.get('CloudFiles', 'SecretKey')
    AKey = config.get('CloudFiles', 'AccessKey')
    bucket = config.get('CloudFiles', 'Bucket')

    conn = S3Connection(AKey, SKey)
    files = yield threads.deferToThread(_getAllFiles, conn, bucket)

    S3fileIds = [x.split("/")[2] for x in files]
    log.msg("Fetched %d files" %(len(S3fileIds)))

    log.msg("Fetching info about all the files")
    d = db.multiget_slice(S3fileIds, "files")

    files_map = {}
    for f in files:
        org, owner, fileId = f.split("/")
        files_map[fileId] = (owner, org)

    res = yield d
    ids = utils.multiSuperColumnsToDict(res)
    fileIds = [x for x in ids.keys() if ids[x] and "owner" not in ids[x]["meta"]]
    log.msg("Out of %d S3 files, found %d files in \'files\' in old format" %( len(S3fileIds), len(fileIds)))

    updated_file_meta = {}
    for fileId in fileIds:
        owner, org = files_map[fileId]
        updated_file_meta[fileId] = {"files":{"meta":{"owner": owner}}}

    log.msg(updated_file_meta)
    yield db.batch_mutate(updated_file_meta)

def main():
    parser = optparse.OptionParser()
    parser.add_option('-d', '--update-data', dest='update', action="store_true")
    options, args = parser.parse_args()

    if options.update:
        log.startLogging(sys.stdout)
        db.startService()

        if options.update:
            d = updateData()

        def finish(x):
            db.stopService()
            reactor.stop()
        d.addErrback(log.err)
        d.addBoth(finish)

        reactor.run()

if __name__ == '__main__':
    main()
