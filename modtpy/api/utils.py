import re


class JsonRegexParser:
    def __init__(self, msg):
        self.parse(msg)

    def get_attributes(self):
        return {s: getattr(self, s) for s in dir(self)
                if not s.startswith("_")
                and not callable(getattr(self, s))}

    def parse(self, msg):
        for name, current_value in self.get_attributes().items():
            found_values = re.findall('"%s":[ "]*([a-zA-Z0-9\._]*)["]*[,}]{1}' % name, msg)
            if found_values:
                setattr(self, name, found_values[0])

    def to_dict(self):
        return self.get_attributes()


class PrinterStatus(JsonRegexParser):
    model_name = None

    class _Status(JsonRegexParser):
        state = None
        build_plate = None
        filament = None
        extruder_temperature = None
        extruder_target_temperature = None

    class _Job(JsonRegexParser):
        id = None
        source = None
        progress = None
        rx_progress = None
        current_line_number = None
        current_gcode_number = None
        file_size = None
        file = None

    class _Time(JsonRegexParser):
        idle = None
        boot = None

    def __init__(self, msg):
        super().__init__(msg)
        self.message = msg
        self.job = self._Job(msg)
        self.status = self._Status(msg)
        self.time = self._Time(msg)

    def to_dict(self):
        return {**super().to_dict(), 'job': self.job.to_dict(), 'status': self.status.to_dict(),
                'time': self.time.to_dict()}


def parse_json(msg):
    return PrinterStatus(msg)
