import logging.config

def configure():
    logging_dict = {
        'version': 1,
        'formatters': {

        },
        'handlers': {
            'default': {
                'class': 'logging.NullHandler'
            }
        },
        'loggers': {

        },
        'root': {
            'handlers': ['default'],
            'level': 'DEBUG',
        }
    }
    logging.config.dictConfig(logging_dict)
