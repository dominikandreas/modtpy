import time

try:
    import click
except ImportError as e:
    print("please install click: e.g. pip3 install -U click")
    raise e

import logging

from modtpy.api import ModT, Mode


def _ensure_connected(callback_function, required_mode=None):
    def wrapper(*args, **kwargs):
        i = 0
        modt = ModT()
        while not modt.is_connected():
            print("\rWaiting for Mod-T connection " + ("." * i), end=" ")
            time.sleep(.5)
            i = (i + 1) % 4
        if required_mode is not None and modt.mode != required_mode:
            if modt.mode == Mode.dfu:
                print("printer is currently in dfu mode. you can put it back into operating mode by restarting it")
                exit()
            elif modt.mode == Mode.operate:
                modt.enter_dfu()

        return callback_function(*args, modt=modt, **kwargs)
    wrapper.__name__ = callback_function.__name__

    return wrapper


def ensure_connected(required_mode_or_function=None):
    if callable(required_mode_or_function):
        f = required_mode_or_function
        return _ensure_connected(f)
    else:
        def __wrapper__(f):
            return _ensure_connected(f, required_mode=required_mode_or_function)

        return __wrapper__


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
@ensure_connected(Mode.operate)
def send_gcode(gcode_path, modt):
    modt.send_gcode(gcode_path)


def loop_print_status(modt):
    while True:
        logging.info(modt.get_status(str_format=True))
        time.sleep(.5)


@cli_root.command()
@ensure_connected(Mode.operate)
def load_filament(modt):
    modt.load_filament()
    loop_print_status(modt)


@cli_root.command()
@ensure_connected(Mode.operate)
def unload_filament(modt):
    modt.unload_filament()
    loop_print_status(modt)


@cli_root.command()
@ensure_connected
def enter_dfu(modt):
    modt.enter_dfu(wait_for_dfu=True)


@cli_root.command()
@ensure_connected(Mode.operate)
def status(modt):
    loop_print_status(modt)


@cli_root.command()
@click.argument("firmware_path", type=click.Path(file_okay=True, dir_okay=False, readable=True))
@ensure_connected(Mode.dfu)
def flash_firmware(firmware_path, modt):
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