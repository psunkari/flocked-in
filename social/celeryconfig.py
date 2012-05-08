# List of modules to import when celery starts.
CELERY_IMPORTS = ("thumbnailer", "celery.task.http")

## Result store settings.
CELERY_IGNORE_RESULT = False
CELERY_RESULT_SERIALIZER = "json"

CELERY_RESULT_BACKEND = "cassandra"
CASSANDRA_SERVERS = ["localhost:9160"]
CASSANDRA_KEYSPACE = "social"
CASSANDRA_COLUMN_FAMILY = "task_results"
CASSANDRA_READ_CONSISTENCY = "ONE"
CASSANDRA_WRITE_CONSISTENCY = "ONE"
CASSANDRA_DETAILED_MODE = False

## Broker settings.
#BROKER_URL = "amqp://guest:guest@localhost:5672//"
#BROKER_TRANSPORT = "sqlalchemy"
BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_USER = "celery"
BROKER_PASSWORD = "celery"
BROKER_VHOST = "voyager"

## Worker settings
## If you're doing mostly I/O you can have more processes,
## but if mostly spending CPU, try to keep it close to the
## number of CPUs on your machine. If not set, the number of CPUs/cores
## available will be used.
#CELERYD_CONCURRENCY = 10
CELERY_SEND_EVENTS = True
CELERY_ANNOTATIONS = {"thumbnailer": {"rate_limit": "6/m"}}
