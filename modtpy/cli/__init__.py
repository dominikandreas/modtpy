import os
import sys
import time
from pathlib import Path

from tqdm.auto import tqdm

from modtpy.api.gcode_optimization import GcodeOptimizer

try:
    import click
except ImportError as e:
    os.system(sys.executable + " -m pip install --user click")
    import click

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
@click.option('--host', default="127.0.0.1", help="The host which the server is exposed to")
def web_server(port, host):
    from modtpy.web import server
    server.run(port=port, host=host)


@cli_root.command()
@click.argument("gcode_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
@ensure_connected(Mode.OPERATE)
def send_gcode(gcode_path, modt):
    modt.send_gcode(gcode_path)
    loop_print_status(modt, tqdm_progress=True)


@cli_root.command()
@click.argument("gcode_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
@click.argument("output_path", default=None, type=click.Path(file_okay=True, dir_okay=True, writable=True, exists=False))
@click.option("-e", "error_threshold", type=click.FLOAT, default=0.15)
def optimize_gcode(gcode_path, output_path, error_threshold):
    assert gcode_path.endswith(".gcode"), "must provide a .gcode file but got " + Path(gcode_path).name
    with open(gcode_path, "r") as f:
        content = f.read()
    optimized = GcodeOptimizer().optimize_gcode(content, error_threshold)
    if output_path is None:
        output_path = gcode_path.replace(".gcode", "_optimized.gcode")
    if os.path.isdir(output_path):
        output_path = output_path + "/" + Path(gcode_path).name
    logging.info("writing result to " + output_path)
    with open(output_path, "w") as f:
        f.write(optimized)


@cli_root.command()
@ensure_connected(Mode.OPERATE)
def reset(modt):
    logging.info("resetting printer")
    modt.reset()
    logging.info("done")


def loop_print_status(modt: ModT, tqdm_progress=False):
    # remove the first two status messages, they are usually garbage and can't be decoded
    for i in range(2):
        modt.format_status_msg(modt.get_status())

    if tqdm_progress:
        bar = tqdm(total=100)

    last_progress = 0
    while True:
        status = modt.get_status()
        status_message = modt.format_status_msg(status, progress=not tqdm_progress)
        progress = status['job']['progress']
        if tqdm_progress and progress is not None:
            try:
                progress = int(progress)
            except ValueError:
                progress = last_progress
            if tqdm_progress:
                bar.update(progress - last_progress)
                last_progress = progress
                bar.set_postfix_str(status_message)
        else:
            logging.info(status_message)
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
@ensure_connected(Mode.OPERATE)
def print_status(modt: ModT):
    loop_print_status(modt, tqdm_progress=True)


@cli_root.command()
@ensure_connected(Mode.OPERATE)
def press_button(modt: ModT):
    modt.press_button()


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
