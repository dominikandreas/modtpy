import os
import time
import json
import usb.core
import usb.util
import tqdm
from zlib import adler32
from subprocess import getoutput

# Adler32 checksum function
# Based on https://gist.github.com/kofemann/2303046
# For some reason, mod-t uses 0, not 1 as the basis of the adler32 sum
BLOCKSIZE = 256 * 1024 * 1024


def adler32_checksum(fname):
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


class ModT:
    def __init__(self):
        self._dev = None

    @property
    def dev(self):
        if self._dev is None:
            self._dev = usb.core.find(idVendor=0x2b75, idProduct=0x0002)
            self._dev.set_configuration()
            if self._dev is None:
                raise ValueError('No Mod-T detected')
        return self._dev

    def enter_dfu(self, wait_for_dfu=True):
        # Mimic the Mod-T desktop utility. First packet is not human readable. Second packet puts Mod-T into DFU mode
        self.dev.write(2, bytearray.fromhex('246a0095ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":7},'
                          '"data":{"command":{"idx":53,"name":"Enter_dfu_mode"}}};')

        self._dev = None
        # Wait for the Mod-T to reattach in DFU mode
        if wait_for_dfu:
            time.sleep(2)

    def load_filament(self):
        self.dev.write(2, bytearray.fromhex('24690096ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":9},'
                          '"data":{"command":{"idx":52,"name":"load_initiate"}}};')

    def unload_filament(self):
        self.dev.write(2, bytearray.fromhex('246c0093ff'))
        self.dev.write(2, '{"transport":{"attrs":["request","twoway"],"id":11},'
                          '"data":{"command":{"idx":51,"name":"unload_initiate"}}};')

    def get_status(self, str_format=False):
        self.dev.write(4, '{"metadata":{"version":1,"type":"status"}}')
        msg = self.read_modt(0x83)

        try:
            msg = json.loads(msg)
        except json.decoder.JSONDecodeError as e:
            if str_format:
                return msg
            else:
                raise e

        if not str_format:
            return msg

        status, job = msg.get("status", {}), msg.get("job", {})
        return (" ".join(map(str,
                             [status.get("state"), "extruder temp:", status.get("extruder_temperature"), "°C / ",
                              status.get("extruder_temperature"), "°C ",
                              "| Job: line number:", job.get("current_line_number")])))

    # Read pending data from MOD-t (bulk reads of 64 bytes)
    def read_modt(self, ep):
        try:
            text = ''.join(map(chr, self.dev.read(ep, 64)))
            fulltext = text
            while len(text) == 64:
                text = ''.join(map(chr, self.dev.read(ep, 64)))
                fulltext = fulltext + text
            return fulltext
        except usb.core.USBError as e:
            return json.dumps(dict(error=str(e)))

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
            pbar.update(current_line_number - pbar.last_line)

            pbar.set_description(
                " ".join(map(str,
                             [status.get("state"), "extruder temp:", status.get("extruder_temperature"), "°C / ",
                              status.get("extruder_temperature"), "°C ",
                              "| Job: line number:", job.get("current_line_number")])))

        print("Gcode sent. executing loop and query mod-t status every 2 seconds")
        while True:
            print_progress(self.get_status(str_format=False))
            time.sleep(2)

    def flash_firmware(self, firmware_path):
        assert self.dev is not None

        firmware_path = os.path.abspath(firmware_path)
        assert os.path.isfile(firmware_path)
        dfu_cmd = "dfu-util -d 2b75:0003 -a 0 -s 0x0:leave -D %s > /tmp/dfu &" % firmware_path
        status_cmd = "tac /tmp/dfu | egrep -m 1 . | sed 's/.*[ \t][ \t]*\([0-9][0-9]*\)%.*/\1/'"

        os.system(dfu_cmd)

        # Loop until the firmware has been written
        while True:
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
            # cleanup our temporary file
            os.remove("/tmp/dfu")

