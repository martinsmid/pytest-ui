import logging
import logging.config

configured = False

def get_logger(name, *args):
    return logging.getLogger('.'.join(['project', name] + list(args)))


class LogWriter(object):
    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        self.logger.debug('STDOUT: (%s)\n', message.strip('\n'))

    def flush(self):
        pass


def configure(filename):
    if configured:
        return False

    logging_dict = {
        'version': 1,
        'formatters': {
            'process': {
                'format': '%(name)-25s  %(levelname)5s  %(message)s',
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
            },
            'project.runner.pipe': {
                'level': 'DEBUG'
            },
            'project.runner.stdout': {
                'handlers': ['logfile'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'project.runner.stderr': {
                'handlers': ['logfile'],
                'level': 'DEBUG',
                'propagate': False,
            }
        },
        'root': {
            'handlers': ['default'],
            'level': 'DEBUG',
        }
    }
    logging.config.dictConfig(logging_dict)
