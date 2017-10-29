import logging
import logging.config
import settings

DEBUG_0 = 0
DEBUG_1 = 1
DEBUG_2 = 2


def get_logger(name, *args):
    return logging.getLogger('.'.join(['pytui', name] + list(args)))


class LogWriter(object):
    def __init__(self, logger):
        self.logger = logger

    def write(self, message):
        self.logger.debug('STDOUT: (%s)\n', message.strip('\n'))

    def flush(self):
        pass


def configure(filename):
    logging_dict = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'process': {
                'format': '%(created)s %(msecs)-15s %(name)-25s  %(levelname)5s  %(message)s',
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
            'pytui': {
                'handlers': ['logfile'],
                'level': DEBUG_0,
            },
            # 'pytui.runner.pipe': {
            #     'level': 'INFO',
            # },
            # 'pytui.runner.stdout': {
            #     'level': 'INFO',
            # },
            # 'pytui.runner.stderr': {
            #     'level': 'INFO',
            # },
            # 'pytui': {
            #     'handlers': ['logfile'],
            #     'level': 'DEBUG',
            # },
        },
        'root': {
            'handlers': ['default'],
            'level': 'CRITICAL',
        }
    }

    for module in settings.DEBUG_MODULES:
        logging_dict['loggers'][module]['level'] = 'DEBUG'
        # logging_dict['loggers'][module]['handlers'] = ['logfile']
        # logging_dict['loggers'][module]['propagate'] = False

    logging.config.dictConfig(logging_dict)
