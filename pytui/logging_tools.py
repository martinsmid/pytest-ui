import logging
import logging.config

configured = False

def get_logger(name, *args):
    return logging.getLogger('.'.join(['project', name] + list(args)))

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
            },
            'project.runner.pipe': {
                'level': 'WARN'
            }

        },
        'root': {
            'handlers': ['default'],
            'level': 'DEBUG',
        }
    }
    logging.config.dictConfig(logging_dict)
