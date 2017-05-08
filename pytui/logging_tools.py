import logging
import logging.config

configured = False

def get_logger(name):
    return logging.getLogger('project.{}'.format(name))


class LogWriter(object):
    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        self.logger.debug('STDOUT: %s', message.strip('\n'))

    def flush(self):
        pass


def configure(filename):
    if configured:
        return False

    logging_dict = {
        'version': 1,
        'formatters': {
            'process': {
                'format': '%(process)10d %(levelname)10s %(message)s',
            }
        },
        'handlers': {
            'default': {
                'class': 'logging.NullHandler'
            },
            'logfile': {
                'class': 'logging.FileHandler',
                'formatter': 'process',
                'filename': filename,
                'mode': 'w+',
            }
        },
        'loggers': {
            'project': {
                'handlers': ['logfile'],
                'level': 'DEBUG',
            }

        },
        'root': {
            'handlers': ['default'],
            'level': 'DEBUG',
        }
    }
    logging.config.dictConfig(logging_dict)
