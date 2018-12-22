import time

try:
    import click
except ImportError as e:
    print("please install click: e.g. pip3 install -U click")
    raise e

import logging
from modtpy.modt import ModT


@click.group()
@click.option('-l', '--debug/--no-debug', default=False)
def cli_root(debug):
    log_level = logging.DEBUG if debug else logging.INFO
    logging.getLogger().setLevel(log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


@cli_root.command()
@click.argument("gcode_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
def send_gcode(gcode_path):
    modt = ModT()
    modt.send_gcode(gcode_path)


def loop_print_status(modt):
    while True:
        logging.info(modt.get_status(str_format=True))
        time.sleep(.5)


@cli_root.command()
def load_filament():
    modt = ModT()
    modt.load_filament()
    loop_print_status(modt)


@cli_root.command()
def unload_filament():
    modt = ModT()
    modt.unload_filament()
    loop_print_status(modt)


@cli_root.command()
def enter_dfu():
    modt = ModT()
    modt.enter_dfu(wait_for_dfu=True)


@cli_root.command()
def status():
    loop_print_status(ModT())


@cli_root.command()
@click.argument("firmware_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
def flash_firmware(firmware_path):
    modt = ModT()
    modt.flash_firmware(firmware_path)


@cli_root.command()
@click.option('-g', '--group', default="sudo")
@click.option('-m', '--mode', default="0664")
def install_udev_rule(group, mode):
    with open("/etc/udev/rules.d", "w") as f:
        for dev_id in ("0002", "0003"):
            f.write("""SUBSYSTEM=="usb", ATTR{idVendor}=="2b75", ATTR{idProduct}=="%s", GROUP="%s", MODE="%s"\n""" %
                    (dev_id, group, mode))


if __name__ == "__main__":
    cli_root()