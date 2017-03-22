import logging
import logging.config

def get_logger(name):
    return logging.getLogger('project.{}'.format(name))

def configure():
    logging_dict = {
        'version': 1,
        'formatters': {

        },
        'handlers': {
            'default': {
                'class': 'logging.NullHandler'
            },
            'logfile': {
                'class': 'logging.FileHandler',
                'filename': 'pytui.log',
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
