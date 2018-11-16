import re


class IncludeAnyFilter(object):

    name = 'include_any'

    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return True

        return False


class IncludeAllFilter(object):

    name = 'include_all'

    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if not regexp.findall(text):
                return False

        return True


class ExcludeFilter(object):

    name = 'exclude'

    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return False

        return True


FILTER_MAP = {
    'include_all': IncludeAllFilter,
    'include_any': IncludeAnyFilter,
    'exclude': ExcludeFilter,
}


def get_filter(config):
    filter_type = config['type']
    if filter_type not in FILTER_MAP:
        raise ValueError("unsupported filter type: {}".format(filter_type))

    filter_cls = FILTER_MAP[filter_type]
    params = {k: v for k, v in config.items() if k != 'type'}
    return filter_cls(**params)
