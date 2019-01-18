class PrinterError(Exception):

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code
        self.payload = payload
        self.__repr__ = self.__str__

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

    def __str__(self):
        return "PrinterError(message=%s, payload='%s')" % (self.message, self.payload)
