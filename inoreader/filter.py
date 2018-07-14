import re


class Filter(object):
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_config(cls, config):
        """
        config: {
            'type': 'include_any',
            'rules': [],
        }
        """
        cls_map = {
            sub_cls.name: sub_cls
            for sub_cls in cls.__subclasses__()
        }

        sub_cls = config['type']
        rules = config['rules']
        return cls_map[sub_cls](rules)

    def validate(self, text):
        raise NotImplementedError


class IncludeAnyFilter(Filter):

    name = 'include_any'

    def __init__(self, rules):
        self.rules = [re.compile(regexp) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return True

        return False


class IncludeAllFilter(Filter):

    name = 'include_all'

    def __init__(self, rules):
        self.rules = [re.compile(regexp) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if not regexp.findall(text):
                return False

        return True


class ExcludeFilter(Filter):

    name = 'exclude'

    def __init__(self, rules):
        self.rules = [re.compile(regexp) for regexp in rules]

    def validate(self, text):
        for regexp in self.rules:
            if regexp.findall(text):
                return False

        return True
