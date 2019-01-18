from modtpy.api.modt import ModT, Mode
from modtpy.api.errors import PrinterError
import logging
from contextlib import contextmanager


def dummy_device_function(f):
    def __inner__(self, *args, **kwargs):
        logging.info("Device.%s called with args: %s, kwargs: %s", f.__name__, str(args), str(kwargs))
        if f.__name__ in self.exceptions:
            raise self.exceptions[f.__name__]

    return __inner__


class DummyUSB:
    exceptions = dict()

    @dummy_device_function
    def __init__(self):
        pass

    @dummy_device_function
    def write(self):
        pass

    @dummy_device_function
    def read(self):
        pass

    @dummy_device_function
    def set_configuration(self):
        pass

    @dummy_device_function
    def __del__(self):
        super()


class VirtualModt(ModT):
    current_mode = Mode.DISCONNECTED

    @classmethod
    def connect(cls):
        cls.current_mode = Mode.OPERATE

    @classmethod
    def disconnect(cls):
        cls.current_mode = Mode.DISCONNECTED

    def enter_dfu(self, wait_for_dfu=False):
        super().enter_dfu(wait_for_dfu=wait_for_dfu)
        self.__class__.current_mode = Mode.DFU

    @contextmanager
    def get_device(self, required_mode=Mode.OPERATE):
        with self.lock():
            if self.mode != required_mode:
                raise PrinterError("%s Device is in %s but need %s" %
                                   (self.__class__.__name__, self.mode, required_mode))

            dev = DummyUSB(idVendor=self.dev_vendor_id, idProduct=required_mode)
            try:
                dev.set_configuration()
            except Exception as e:
                raise PrinterError(message=e, payload="Unable to access printer: %s" % e)
            try:
                yield dev
            finally:
                del dev

    @property
    def mode(self):
        return self.__class__.current_mode


