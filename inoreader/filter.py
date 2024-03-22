import re

_FILTERS = {}


def register_filter(name, override=False):
    def wrap(cls):
        global _FILTERS
        if name not in _FILTERS or override:
            _FILTERS[name] = cls

        return cls

    return wrap


@register_filter("include_any")
class IncludeAnyFilter(object):
    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return True

        return False


@register_filter("include_all")
class IncludeAllFilter(object):
    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if not regexp.findall(text):
                return False

        return True


@register_filter("exclude")
class ExcludeFilter(object):
    def __init__(self, rules):
        self.rules = [re.compile(regexp, re.IGNORECASE) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return False

        return True


def get_filter(config):
    filter_type = config["type"]
    if filter_type not in _FILTERS:
        raise ValueError("unsupported filter type: {}".format(filter_type))

    filter_cls = _FILTERS[filter_type]
    params = {k: v for k, v in config.items() if k != "type"}
    return filter_cls(**params)
