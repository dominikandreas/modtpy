import os
import usb
import threading
from contextlib import contextmanager
import fasteners

MUTEX_PATH = os.sep.join([os.path.expanduser("~"), ".modtpy.lock"])


class Mode:
    # Mode values are used for usb product id
    DISCONNECTED = -1
    DFU = 0x0003
    OPERATE = 0x0002

    @staticmethod
    def to_string(mode):
        return {Mode.DFU: "DFU", Mode.OPERATE: "operate"}.get(mode, "disconnected")


_lock = threading.Lock()


class USBDevice:
    dev_vendor_id = 0x000

    @contextmanager
    def lock(self, timeout=0.5):
        process_lock = fasteners.InterProcessLock(MUTEX_PATH)
        proc_acquired = process_lock.acquire(timeout=timeout)
        thread_acquired = _lock.acquire(timeout=timeout)
        try:
            if not proc_acquired or not thread_acquired:
                raise TimeoutError("Couldn't acquire lock for %s" % MUTEX_PATH)
            yield
        finally:
            if proc_acquired:
                process_lock.release()
            if thread_acquired:
                _lock.release()

    @contextmanager
    def get_device(self, required_mode=Mode.OPERATE):
        with self.lock():
            if self.mode != required_mode:
                raise RuntimeError("Device is in %s but need %s" %
                                   (Mode.to_string(self.mode), Mode.to_string(required_mode)))

            dev = usb.core.find(idVendor=self.dev_vendor_id, idProduct=required_mode)
            try:
                dev.set_configuration()
                yield dev
            finally:
                dev.reset()
                del dev

    @property
    def mode(self):
        if usb.core.find(idVendor=self.dev_vendor_id, idProduct=Mode.OPERATE):
            return Mode.OPERATE
        elif usb.core.find(idVendor=self.dev_vendor_id, idProduct=Mode.DFU):
            return Mode.DFU
        return Mode.DISCONNECTED

    @classmethod
    def _get_status(cls, device):
        raise NotImplementedError

    def get_status(self, device=None):
        if self.mode is Mode.DISCONNECTED:
            msg = dict(status=dict(state="disconnected"))
        elif self.mode is Mode.DFU:
            msg = dict(status=dict(state="DFU mode"))
        else:
            if device is not None:
                msg = self._get_status(device)
            else:
                with self.get_device(Mode.OPERATE) as dev:
                    msg = self._get_status(dev)

        return msg
