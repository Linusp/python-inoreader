class NotLoginError(ValueError):
    def __repr__(self):
        return "<NotLoginError>"


class APIError(ValueError):
    def __repr__(self):
        return "<APIError>"
