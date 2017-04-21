import re


def get_filter_regex(filter_value):
    if not filter_value:
        return None

    regexp_str = '.*?'.join(list(iter(
        filter_value.replace('.', '\.').replace(r'\\', '\\\\')
    )))
    return re.compile(regexp_str, re.UNICODE + re.IGNORECASE)
