import os
import sys


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


res_dir = os.path.abspath(os.path.dirname(__file__))

is_64_bit = sys.maxsize > 2 ** 32

lib_usb_dir = res_dir + "/libusb/%s/dll/" % ("MS64" if is_64_bit else "MS32")

firmwares_dir = res_dir + "/firmwares/"

dfu_util_dir = res_dir + "/dfu_util/"


def get_firmwares():
    return [firmwares_dir + "/" + e
            for e in os.listdir(firmwares_dir) + os.listdir(os.getcwd())
            if e.lower().endswith(".dfu")]


if __name__ == "__main__":
    for firmware in get_firmwares():
        print(firmware)
