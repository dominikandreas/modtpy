import logging
logging.getLogger().setLevel(logging.DEBUG)

import unittest
import time
import multiprocessing
from testing import dummy_usb


class ParallelModTUser:
    def __init__(self, start=True):
        self.device = dummy_usb.VirtualModt()
        self.process = multiprocessing.Process(target=self.block_device_background, kwargs=dict(device=self.device))
        self.process.daemon = True
        self._run_Q = multiprocessing.Queue()
        self._run_Q.put(True)
        if start:
            self._run = True
            self.process.start()

    def should_run(self):
        should_run = self._run_Q.get()
        self._run_Q.put(should_run)
        return should_run

    def block_device_background(self, device):
        device.connect()
        with device.get_device():
            while self.should_run():
                time.sleep(.1)

    def stop(self):
        self._run_Q.get()
        self._run_Q.put(False)


class ModTTests(unittest.TestCase):
    def test_mutex(self):
        modt = dummy_usb.VirtualModt()
        modt.connect()
        modt_user = ParallelModTUser(start=True)

        raised_timeout_error = False

        time.sleep(2)
        try:
            # enter dfu needs dev but can't reserve mutex because we already have it
            with modt.get_device() as dev:
                logging.warning("acquired device successfully")
        except TimeoutError:
            raised_timeout_error = True
        finally:
            modt_user.stop()

        assert raised_timeout_error, "should not have been able to acquire device"

    def test_command_id_increment(self):
        modt = dummy_usb.VirtualModt()
        modt.connect()

        assert modt.running_id == 1

        with modt.get_device() as dev:
            modt._send_command(dev, "load_initiate")

        assert modt.running_id == 3

        with modt.get_device() as dev:
            modt._send_command(dev, "unload_initiate")

        del modt
        modt = dummy_usb.VirtualModt
        assert modt.running_id == 5

    def test_set_dfu_mode(self):
        from modtpy.api.modt import ModT, Mode
        modt = ModT()
        while modt.mode != Mode.OPERATE:
            print("please unplug modt and plug it back in after the light turns of to continue testing")
            time.sleep(1)

        assert modt.mode == Mode.OPERATE
        modt.enter_dfu(wait_for_dfu=True)
        assert modt.mode == Mode.DFU
        while modt.mode != Mode.OPERATE:
            print("please unplug modt and plug it back in after the light turns of to continue testing")
            time.sleep(1)


if __name__ == "__main__":
    unittest.main()