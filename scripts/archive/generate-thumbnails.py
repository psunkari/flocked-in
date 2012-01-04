import os
import sys
import boto
import time
import json
import tempfile
import optparse
import PythonMagick

sys.path.append(os.getcwd())
from social import config, constants


MEDIA_MIME = ['image/jpg', 'image/jpeg', 'image/gif', 'image/png', 'application/pdf']


def get_count():
    secretKey =  config.get('CloudFiles', 'SecretKey')
    accessKey =  config.get('CloudFiles', 'AccessKey')
    thumbnailsQueue = config.get('CloudFiles', 'ThumbnailsQueue')
    sqsConn = boto.connect_sqs(accessKey, secretKey)
    queue = sqsConn.get_queue(thumbnailsQueue)
    print '%s -- %s' %(thumbnailsQueue, queue.count())


def generate_thumbnails(dry_run=True):
    def _generate_thumbnail(filename, size, thumbKey, content_type, thumbnailsBucket):
        tmpFile = tempfile.NamedTemporaryFile()
        image = PythonMagick.Image(filename)
        image.scale(size)
        image.write(tmpFile.name)
        k1 = thumbnailsBucket.new_key(thumbKey)
        headers = {'Content-Type': str(content_type)}
        k1.set_contents_from_file(tmpFile, headers)
        tmpFile.close()

    secretKey =  config.get('CloudFiles', 'SecretKey')
    accessKey =  config.get('CloudFiles', 'AccessKey')
    bucketName = config.get('CloudFiles', 'Bucket')
    thumbnailsBucket = config.get('CloudFiles', 'ThumbnailsBucket')
    thumbnailsQueue = config.get('CloudFiles', 'ThumbnailsQueue')

    if not (secretKey and accessKey) and not dry_run:
        raise Exception("MISSING CONFIG")

    sqsConn = boto.connect_sqs(accessKey, secretKey)
    s3Conn = boto.connect_s3(accessKey, secretKey)

    thumbnailsBucket = s3Conn.get_bucket(thumbnailsBucket)
    queue = sqsConn.get_queue(thumbnailsQueue)
    sleep = 1

    while 1:
        done_work = False
        for message in queue.get_messages():
            meta = json.loads(message.get_body())
            key = meta['key']
            bucket = meta['bucket']
            filename = meta['filename']
            content_type = meta['content-type']
            isProfilePic = meta.get('is-profile-pic', False)
            isLogo = meta.get('is-logo', False)
            isAttachment = meta.get('is-attachment', False)

            if content_type in MEDIA_MIME:
                #TODO: cache the buckets
                bucket = s3Conn.get_bucket(bucketName)
                k = bucket.get_key(key)
                if k is None:
                    queue.delete_message(message)
                    continue
                done_work= True

                fp = tempfile.NamedTemporaryFile()
                k.get_file(fp)

                large = constants.LOGO_SIZE_LARGE if isLogo else constants.AVATAR_SIZE_LARGE
                medium = constants.LOGO_SIZE_MEDIUM if isLogo else constants.AVATAR_SIZE_MEDIUM
                small = constants.LOGO_SIZE_SMALL if isLogo else constants.AVATAR_SIZE_SMALL

                largeThumbKey = "large/%s" %(key)
                mediumThumbKey = "medium/%s" %(key)
                smallThumbKey = "small/%s" %(key)

                _generate_thumbnail(fp.name, large, largeThumbKey, content_type, thumbnailsBucket)
                _generate_thumbnail(fp.name, medium, mediumThumbKey, content_type, thumbnailsBucket)
                _generate_thumbnail(fp.name, small, smallThumbKey, content_type, thumbnailsBucket)

                fp.close() #temp file is destroyed.
            queue.delete_message(message)
        if not done_work:
            sleep = 60 if sleep > 30 else (sleep*2)
        else:
            sleep = 1
        time.sleep(sleep) # prevents busy loop


if __name__== '__main__':
    parser = optparse.OptionParser()
    parser.add_option('--run', dest="run", action="store_true", default=False,
                      help="start processing the queued requests")
    parser.add_option('--get-count', dest="get_count", action="store_true",
                      help='get queue count')

    options, args = parser.parse_args()

    if options.get_count:
        get_count()
    elif options.run:
        generate_thumbnails(dry_run=False)


