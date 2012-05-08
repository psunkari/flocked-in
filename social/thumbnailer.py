import Image, ImageOps
import tempfile
import math

import boto
from boto.s3.key            import Key
from boto.s3.bucket         import Bucket
from boto.s3.connection     import S3Connection

from celery import Celery

import celeryconfig

celery = Celery()
celery.config_from_object(celeryconfig)
task = celery.task

@task(name="thumbnailer")
def process_thumbnail(config, orgId, userId, fileId, fileType, task_id=None):
    logger = process_thumbnail.get_logger()

    SKey = config.get('CloudFiles', 'SecretKey')
    AKey = config.get('CloudFiles', 'AccessKey')
    bucket =  config.get('CloudFiles', 'Bucket')
    domain = "s3.amazonaws.com"

    conn = S3Connection(AKey, SKey, host=domain, is_secure=True)
    bucket = Bucket(conn, bucket)

    sUrl = "%s/%s/%s" % (orgId, userId, fileId)
    dUrl = "%s/%s/thumbs/%s" % (orgId, userId, fileId)
    sKey = Key(bucket, sUrl)
    dKey = Key(bucket, dUrl)

    _file = tempfile.NamedTemporaryFile()
    sKey.get_contents_to_file(_file)
    _file.seek(0)
    logger.debug("Downloaded from S3")
    im = Image.open(_file)
    orig_size = im.size

    orig_ratio = orig_size[0]/orig_size[1]
    thumb_height = 128
    thumb_width = thumb_height*orig_ratio
    thumb_width = thumb_width if thumb_width > 512 else 512

    size = int(math.ceil(thumb_width)), thumb_height
    im.thumbnail(size, Image.ANTIALIAS)
    thumbfile = tempfile.TemporaryFile()

    if fileType == "image/png":
        _format = "PNG"
    elif fileType == "image/jpeg":
        _format = "JPEG"
    else:
        _format = "JPEG"
    im.save(thumbfile, _format)
    logger.debug("Thumbnail Generated")
    thumbfile.seek(0)
    dKey.set_contents_from_file(thumbfile)
    logger.debug("Uploaded to S3")
    return 1
