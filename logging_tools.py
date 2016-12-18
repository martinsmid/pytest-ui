import logging.config

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
                'filename': 'putr.log',
                'mode': 'w+',
            }
        },
        'loggers': {
            '__main__': {
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
