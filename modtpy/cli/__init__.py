import time

try:
    import click
except ImportError as e:
    print("please install click: e.g. pip3 install -U click")
    raise e

import logging

from modtpy.api.modt import ModT, Mode
from modtpy.cli.tools import ensure_connected, get_user_choice


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
@click.option('--port', default=5000, help='Port the server should be running on.')
def web_server(port):
    from modtpy.web import server
    server.run(port=port)


@cli_root.command()
@click.argument("gcode_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
@ensure_connected(Mode.OPERATE)
def send_gcode(gcode_path, modt):
    modt.send_gcode(gcode_path)


def loop_print_status(modt: ModT):
    while True:
        logging.info(modt.format_status_msg(modt.get_status()))
        time.sleep(.5)


@cli_root.command()
@ensure_connected(Mode.OPERATE)
def load_filament(modt):
    modt.load_filament()
    loop_print_status(modt)


@cli_root.command()
@ensure_connected(Mode.OPERATE)
def unload_filament(modt: ModT):
    modt.unload_filament()
    loop_print_status(modt)


@cli_root.command()
@ensure_connected
def enter_dfu(modt):
    modt.enter_dfu(wait_for_dfu=True)


@cli_root.command()
@ensure_connected(Mode.OPERATE)
def status(modt: ModT):
    loop_print_status(modt)


@cli_root.command()
@click.option("-f", "--firmware_path", default=None, type=click.Path(file_okay=True, dir_okay=False, readable=True))
@ensure_connected(Mode.DFU)
def flash_firmware(firmware_path, modt: ModT):
    if firmware_path is None:
        from modtpy.res import get_firmwares

        firmware_path = get_user_choice(choices=get_firmwares(), prompt="Please select one of the available firmwares:")
    modt.flash_firmware(firmware_path)


@cli_root.command()
@click.option('-g', '--group', default="sudo")
@click.option('-m', '--mode', default="0664")
def install_udev_rule(group, mode):
    with open("/etc/udev/rules.d/51-modt.rules", "w") as f:
        for dev_id in ("0002", "0003"):
            f.write("""SUBSYSTEM=="usb", ATTR{idVendor}=="2b75", ATTR{idProduct}=="%s", GROUP="%s", MODE="%s"\n""" %
                    (dev_id, group, mode))


if __name__ == "__main__":
    cli_root()
