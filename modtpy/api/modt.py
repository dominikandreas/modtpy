import os
import sys
import time
import json
from io import StringIO
from os import PathLike
from typing import Union, BinaryIO

import usb.core
import usb.util
import tqdm
from zlib import adler32

import threading
import logging

from modtpy import api
from modtpy.api.usb import USBDevice, Mode
from modtpy.api.utils import TqdmLogger

from modtpy.res import lib_usb_dir, dfu_util_dir

BLOCKSIZE = 256 * 1024 * 1024

if os.name == 'nt':
    is_64_bit = sys.maxsize > 2 ** 32
    print("using %s" % lib_usb_dir)
    assert os.path.isdir(lib_usb_dir)
    os.environ['PATH'] = os.pathsep.join([os.environ['PATH'], lib_usb_dir, dfu_util_dir])


def adler32_checksum(data: bytes):
    # Adler32 checksum function based on https://gist.github.com/kofemann/2303046
    # For some reason, mod-t uses 0, not 1 as the basis of the adler32 sum
    adler_sum = adler32(data, 0)
    if adler_sum < 0:
        adler_sum += 2 ** 32
    return adler_sum


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


class Endpoints:
    COMMAND_READ = 0x81
    COMMAND_WRITE = 0x2
    BASIC_READ = 0x83
    BASIC_WRITE = 0x4


class ModT(USBDevice):
    dev_vendor_id = 0x2b75
    running_id = 1

    def __init__(self):
        self.current_gcode_path = None
        self.current_gcode_len = None
        self.last_status = dict(status=dict(state="disconnected"))
        self.last_status_time = 0
        self.status_poll_interval = .5

    def run_status_loop(self, daemon=False):
        if daemon:
            while True:
                try:
                    self.last_status = self.get_status()
                    self.last_status_time = time.time()
                except Exception as e:
                    logging.debug("couldn't get status: %s" % e)
                time.sleep(self.status_poll_interval)
        else:
            thread = threading.Thread(target=self.run_status_loop, kwargs=dict(daemon=True))
            thread.daemon = True
            thread.start()
            return thread

    def has_correct_mode(self, required_mode=None):
        return required_mode is None or self.mode == required_mode

    @classmethod
    def _send_command(cls, device, command_name, arguments=None):
        checksum, payload = api.modt_commands.get_payload(command_name, cls.running_id, args=arguments)
        device.write(Endpoints.COMMAND_WRITE, bytearray.fromhex(checksum))
        device.write(Endpoints.COMMAND_WRITE, payload)
        cls.running_id += 2

    @classmethod
    def _exec_command(cls, device, command_name, arguments=None):
        cls._send_command(device, command_name, arguments)
        # first 5 chars belong to checksum
        return cls._read_response(device, Endpoints.COMMAND_READ)[5:]

    def enter_dfu(self, wait_for_dfu=False):
        if self.mode is Mode.DFU:
            return

        with self.get_device() as dev:
            self._send_command(dev, "Enter_dfu_mode")

        # Wait for the Mod-T to reattach in DFU mode
        if wait_for_dfu:
            time.sleep(wait_for_dfu if isinstance(wait_for_dfu, (int, float)) else 2)

    def load_filament(self):
        with self.get_device() as dev:
            self._send_command(dev, "load_initiate")

    def unload_filament(self):
        with self.get_device() as dev:
            self._send_command(dev, "unload_initiate")

    def format_status_msg(self, msg: dict, progress=True):
        status, job = msg.get("status", {}), msg.get("job", {})
        state = status.get("state", self.mode)
        for key, value in STATUS_STRINGS.items():
            state = str(state).replace(key, value)

        return (" | ".join(map(str, [state,
                                     "Temp: %s°C / %s °C" % (status.get("extruder_temperature", "?"),
                                                             status.get("extruder_target_temperature", "?")),
                                     *(["Progress: %s%%" % job.get('progress', "?")] if progress else [])
                                     ])))

    def _get_status(self, device, handle_exception=True, as_dict=True):
        device.write(Endpoints.BASIC_WRITE, '{"metadata":{"version":1,"type":"status"}}')
        msg = self._read_response(device, Endpoints.BASIC_READ)
        msg = api.utils.parse_json(msg)
        if as_dict:
            msg = msg.to_dict()
            msg["msg_str_format"] = self.format_status_msg(msg)
        return msg

    def get_status(self, device=None):
        if (time.time() - self.last_status_time) < self.status_poll_interval:
            print("returning cached status from t=%s" % self.last_status_time)
            return self.last_status
        else:
            return super().get_status(device=device)

    @staticmethod
    def _read_response(device, endpoint):
        # Read pending data from MOD-t (bulk reads of 64 bytes)
        text = ''.join(map(chr, device.read(endpoint, 64)))
        fulltext = text
        while len(text) == 64:
            text = ''.join(map(chr, device.read(endpoint, 64)))
            fulltext = fulltext + text
        logging.debug("read data from device: " + fulltext)
        return fulltext

    def read_response(self, endpoint):
        assert endpoint in (Endpoints.BASIC_READ, Endpoints.COMMAND_READ)

        try:
            with self.get_device(Mode.OPERATE) as dev:
                return self._read_response(dev, endpoint)
        except usb.core.USBError as e:
            return json.dumps(dict(error=str(e)))

    def reset(self, wait_for_reboot=False):
        with self.get_device() as dev:
            self._send_command(dev, 'Reset_printer')

        if wait_for_reboot:
            time.sleep(3)

    def press_button(self):
        with self.get_device() as dev:
            self._send_command(dev, 'gcode_process_command',
                               arguments=dict(command=[ord(c) for c in api.modt_commands.press_button_gcode] + [0]))

    def send_gcode(self, gcode_file: Union[PathLike, BinaryIO], logger=None):
        if logger is None:
            logger = logging.getLogger()

        logger.info("resetting device to flush old jobs")
        self.reset(wait_for_reboot=True)
        logger.info("done")

        def update_progress(progress):
            self.last_status.update(dict(status=dict(state="STATE_FILE_RX"), job=dict(progress=progress)))
            self.last_status_time = time.time()

        update_progress(0)
        if type(gcode_file) is str and os.path.isfile(gcode_file):
            with open(gcode_file, "rb") as f:
                gcode = f.read()
        elif hasattr(gcode_file, "read"):
            gcode = gcode_file.read()
        else:
            raise ValueError("Invalid gcode_file %s" % gcode_file)

        checksum = adler32_checksum(gcode)
        gcode_file_size = len(gcode)

        update_progress(0)

        # The following came from a usb-dump and is probably not necessary
        # Some commands are human readable some are maybe checksums
        """
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

        """

        with self.get_device(Mode.OPERATE) as dev:
            logger.debug(self._exec_command(dev, "bio_get_version"))
            logger.debug(self.format_status_msg(self.get_status(device=dev)))
            logger.debug(self._exec_command(dev, "wifi_client_get_status", arguments=dict(interface_t=0)))
            logger.debug(self._exec_command(dev, "bio_get_version"))
            for i in range(2):
                logger.debug(self.format_status_msg(self.get_status(device=dev)))
                update_progress(0)

            # prepare printer for sending gcode
            dev.write(Endpoints.BASIC_WRITE,
                      '{"metadata":{"version":1,"type":"file_push"},"file_push":'
                      '{"size":%i,"adler32":%i,"job_id":"","file":"%s"}}' % (gcode_file_size, checksum, gcode_file))

            # Write gcode in batches of 20 bulk writes, each 5120 bytes. Read mod-t status between these 20 bulk writes
            start = counter = 0
            total = len(gcode)

            tqdm_out = TqdmLogger(logger)

            with tqdm.tqdm(total=len(gcode), file=tqdm_out) as pbar:
                while True:
                    # set status time so that old (cached) status is returned
                    end = start + 5120
                    block = gcode[start:end]

                    if counter > 0 and counter % 20 == 0:
                        self._read_response(dev, Endpoints.BASIC_READ)

                    dev.write(Endpoints.BASIC_WRITE, block)

                    counter += 1
                    start += 5120
                    update_progress(progress=int(start / len(gcode) * 100))

                    pbar.update(5120)
                    pbar.set_description("Sent bytes %i / %i" % (end, total))
                    if start > gcode_file_size:
                        break
            logger.info("upload complete")

    def flash_firmware(self, firmware_path, override_confirm=False):
        firmware_path = os.path.abspath(firmware_path)
        assert os.path.isfile(firmware_path)
        self.get_device(Mode.DFU)
        if not override_confirm:
            import click
            click.confirm("Are you sure you wish to flash %s to the device?" % firmware_path)

        dfu_cmd = "dfu-util -d 2b75:0003 -a 0 -s 0x0:leave -D %s " % firmware_path
        os.system(dfu_cmd)
