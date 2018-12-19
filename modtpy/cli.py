import click
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


@cli_root.command()
def load_filament():
    modt = ModT()
    modt.load_filament()


@cli_root.command()
def unload_filament():
    modt = ModT()
    modt.unload_filament()


@cli_root.command()
def enter_dfu():
    modt = ModT()
    modt.enter_dfu(wait_for_dfu=True)


@cli_root.command()
def status():
    modt = ModT()
    logging.info(modt.get_status(str_format=True))


