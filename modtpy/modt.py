import os
import sys
import time
import json
import usb.core
import usb.util
import tqdm
from zlib import adler32
from subprocess import getoutput

BLOCKSIZE = 256 * 1024 * 1024

if os.name == 'nt':
    is_64_bit = sys.maxsize > 2 ** 32
    libusb_path = os.path.abspath(os.path.dirname(__file__) + "/libusb/%s/dll/" % ("MS64" if is_64_bit else "MS32"))
    # print("using %s" % libusb_path)
    os.environ['PATH'] = os.environ['PATH'] + os.pathsep + libusb_path


def adler32_checksum(fname):
    # Adler32 checksum function based on https://gist.github.com/kofemann/2303046
    # For some reason, mod-t uses 0, not 1 as the basis of the adler32 sum
    asum = 0
    f = open(fname, "rb")
    while True:
        data = f.read(BLOCKSIZE)
        if not data:
            break
        asum = adler32(data, asum)
        if asum < 0:
            asum += 2 ** 32
    f.close()
    return asum


STATUS_STRINGS = dict(STATE_LOADFIL_HEATING="Load filament: heating",
                      STATE_LOADFIL_EXTRUDING="Load filament: extruding",
                      STATE_REMFIL_HEATING="Unload filament: heating",
                      STATE_REMFIL_RETRACTING="Unload filament: retracting",
                      STATE_IDLE="Idle",
                      STATE_FILE_RX="Receiving GCode",
                      STATE_JOB_QUEUED="Job queued",
                      STATE_JOB_PREP="Preparing Job",
                      STATE_HOMING_XY="Calibrating X/Y axis",
                      STATE_HOMING_HEATING="Heating up",
                      STATE_HOMING_Z_ROUGH="Calibrating Z axis rough",
                      STATE_HOMING_Z_FINE="Calibrating Z axis fine",
                      STATE_BUILDING="Printing",
                      STATE_EXEC_PAUSE_CMD="Pausing",
                      STATE_PAUSED="Paused",
                      STATE_UNPAUSED="Resuming",
                      STATE_MECH_READY="Print finished")


class Mode:
    dfu, operate, disconnected = 0, 1, 2


def _ensure_connected(callback_function, required_mode=None):
    def wrapper(self, *args, **kwargs):
        if not self.is_connected():
            raise RuntimeError("Mod-T is not connected")
        if required_mode is not None and self.mode != required_mode:
            if self.mode == Mode.dfu:
                print("printer is currently in dfu mode. you can put it back into operating mode by restarting it")
                exit()
            elif self.mode == Mode.operate:
                self.enter_dfu()

        return callback_function(self, *args, **kwargs)

    return wrapper


def ensure_connected(required_mode_or_function=None):
    if callable(required_mode_or_function):
        f = required_mode_or_function
        return _ensure_connected(f)
    else:
        def __wrapper__(f):
            return _ensure_connected(f, required_mode=required_mode_or_function)

        return __wrapper__


class ModT:
    dev_id_operate = 0x0002
    dev_id_dfu = 0x0003
    dev_vendor_id = 0x2b75

    def __init__(self):
        self._dev = None
        self.dev_id = self.dev_id_operate

    @property
    def dev_id(self):
        return self._dev_id

    @dev_id.setter
    def dev_id(self, value):
        self._dev_id = value
        self._dev = None

    @property
    def dev(self):
        if self._dev is None:
            self._dev = usb.core.find(idVendor=self.dev_vendor_id, idProduct=self.dev_id)
            if self._dev is not None:
                self._dev.set_configuration()
        return self._dev

    @staticmethod
    def is_connected():
        return (usb.core.find(idVendor=ModT.dev_vendor_id, idProduct=ModT.dev_id_operate) or
                usb.core.find(idVendor=ModT.dev_vendor_id, idProduct=ModT.dev_id_dfu))

    @property
    def mode(self):
        if usb.core.find(idVendor=ModT.dev_vendor_id, idProduct=ModT.dev_id_operate):
            return Mode.operate
        elif usb.core.find(idVendor=ModT.dev_vendor_id, idProduct=ModT.dev_id_dfu):
            return Mode.dfu
        else:
            return Mode.disconnected

    @ensure_connected
    def enter_dfu(self, wait_for_dfu=True):
        if self.mode is Mode.dfu:
            return

        self.dev_id = self.dev_id_operate

        assert self.dev is not None, "No Mod-T connected"

        # Mimic the Mod-T desktop utility. First packet is not human readable. Second packet puts Mod-T into DFU mode
        self.dev.write(2, bytearray.fromhex('246a0095ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":7},'
                          '"data":{"command":{"idx":53,"name":"Enter_dfu_mode"}}};')

        self.dev_id = self.dev_id_dfu
        # Wait for the Mod-T to reattach in DFU mode
        if wait_for_dfu:
            time.sleep(2)

    @ensure_connected(Mode.operate)
    def load_filament(self):
        self.dev.write(2, bytearray.fromhex('24690096ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":9},'
                          '"data":{"command":{"idx":52,"name":"load_initiate"}}};')

    @ensure_connected(Mode.operate)
    def unload_filament(self):
        self.dev.write(2, bytearray.fromhex('246c0093ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":11},'
                          '"data":{"command":{"idx":51,"name":"unload_initiate"}}};')

    @ensure_connected(Mode.operate)
    def get_status(self, str_format=False):
        self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
        msg = self.read_modt(0x83)

        try:
            msg = json.loads(msg)
        except json.decoder.JSONDecodeError as e:
            if str_format:
                return msg
            else:
                raise RuntimeError("Unable to decode printer message: %s: JSONDecodeError: %s" % (msg, e))

        if not str_format:
            return msg

        status, job = msg.get("status", {}), msg.get("job", {})
        state = status.get("state")
        for key, value in STATUS_STRINGS.items():
            state = state.replace(key, value)

        return (" ".join(map(str,
                             ["State: " + state, "| extruder temp:", status.get("extruder_temperature"), "°C / ",
                              status.get("extruder_target_temperature"), "°C ",
                              "| Job: line number:", job.get("current_line_number")])))

    @ensure_connected(Mode.operate)
    def read_modt(self, ep):
        # Read pending data from MOD-t (bulk reads of 64 bytes)
        try:
            text = ''.join(map(chr, self.dev.read(ep, 64)))
            fulltext = text
            while len(text) == 64:
                text = ''.join(map(chr, self.dev.read(ep, 64)))
                fulltext = fulltext + text
            return fulltext
        except usb.core.USBError as e:
            return json.dumps(dict(error=str(e)))

    @ensure_connected(Mode.operate)
    def send_gcode(self, gcode_path):
        if not os.path.isfile(gcode_path):
            raise RuntimeError(gcode_path + " not found")

        gcode_file_size = os.path.getsize(gcode_path)

        # Get the adler32 checksum of the gcode file
        checksum = adler32_checksum(gcode_path)

        with open(gcode_path, "rb") as f:
            gcode = f.read()

        # These came from usb dump.
        # Some commands are human readable some are maybe checksums
        self.dev.write(2, bytearray.fromhex('246a0095ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":3},'
                          '"data":{"command":{"idx":0,"name":"bio_get_version"}}};')
        print(self.read_modt(0x81))

        self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
        print(self.read_modt(0x83))

        self.dev.write(2, bytearray.fromhex('248b0074ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":5},'
                          '"data":{"command":{"idx":22,"name":"wifi_client_get_status","args":{"interface_t":0}}}};')
        print(self.read_modt(0x81))

        self.dev.write(2, bytearray.fromhex('246a0095ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":7},'
                          '"data":{"command":{"idx":0,"name":"bio_get_version"}}};')
        print(self.read_modt(0x81))

        for _ in range(2):
            self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
            print(self.read_modt(0x83))

        # Start writing actual gcode
        # File size and adler32 checksum calculated earlier
        self.dev.write(4, '{"metadata":{"version":1,"type":"file_push"},"file_push":{"size":'
                       + str(gcode_file_size) + ',"adler32":' + str(checksum) + ',"job_id":""}}')

        # Write gcode in batches of 20 bulk writes, each 5120 bytes. Read mod-t status between these 20 bulk writes
        start = counter = 0
        total = len(gcode)

        with tqdm.tqdm(total=len(gcode)) as pbar:
            while True:
                if start + 5120 - 1 > gcode_file_size - 1:
                    end = gcode_file_size
                else:
                    end = start + 5120
                block = gcode[start:end]
                counter += 1
                if counter >= 20:
                    temp = self.read_modt(0x83)
                    counter = 0

                # self.dev.write(4, block)
                self.dev.write(4, block)
                if start == 0:
                    temp = self.read_modt(0x83)
                start = start + 5120
                pbar.update(5120)
                pbar.set_description("Sent bytes %i / %i" % (end, total))
                if start > gcode_file_size:
                    break

        pbar = tqdm.tqdm(total=len(gcode.split(b"\n")), unit="l")
        pbar.last_line = 0

        def print_progress(msg):
            status, job = msg.get("status", {}), msg.get("job", {})
            current_line_number = job.get("current_line_number")
            if current_line_number is not None:
                pbar.update(current_line_number - pbar.last_line)
                pbar.last_line = current_line_number

            state = status.get("state", "?")
            for key, value in STATUS_STRINGS.items():
                state = state.replace(key, value)

            pbar.set_description(
                " ".join(map(str,
                             ["State: " + state, "| extruder temp:", status.get("extruder_temperature", "?"), "°C / ",
                              status.get("extruder_target_temperature", "?"), "°C ",
                              "| Job: line number:", job.get("current_line_number", "?")])))

        print("Gcode sent. executing loop and query mod-t status every 2 seconds")
        while True:
            try:
                print_progress(self.get_status(str_format=False))
                time.sleep(2)
            except Exception:
                import traceback
                traceback.print_exc()

    @ensure_connected(Mode.dfu)
    def flash_firmware(self, firmware_path):
        firmware_path = os.path.abspath(firmware_path)
        assert os.path.isfile(firmware_path)
        dfu_cmd = "dfu-util -d 2b75:0003 -a 0 -s 0x0:leave -D %s > /tmp/dfu &" % firmware_path
        status_cmd = "tac /tmp/dfu | egrep -m 1 . | sed 's/.*[ \t][ \t]*\([0-9][0-9]*\)%.*/\1/'"

        os.system(dfu_cmd)

        # Loop until the firmware has been written
        while True:
            try:
                # Steal just the progress value from the file
                progress = getoutput(status_cmd)
                if "Transitioning" in progress:
                    # We won't always capture the 100% progress indication, so we force it
                    progress = 100
                    print(progress)
                    # exit the loop
                    break

                print(progress)
                # the dfu-util write is kinda slow, let's not waste too much cpu time
                time.sleep(1)
            finally:
                # cleanup our temporary file
                os.remove("/tmp/dfu")


if __name__ == "__main__":
    modt = ModT()
    while True:
        print("\r" + modt.get_status(str_format=True), end="")
        time.sleep(1)
