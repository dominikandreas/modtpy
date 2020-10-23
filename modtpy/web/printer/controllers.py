from flask import Blueprint, jsonify
from modtpy.api.modt import ModT, Mode
from modtpy.cli.tools import ensure_connected

printer = Blueprint('printer', __name__)
modt = ModT()
modt.run_status_loop()


@printer.route('/status')
def status():
    mode = Mode.to_string(modt.mode)
    status = modt.get_status()
    return jsonify(mode=mode, status=status)


@printer.route('/load-filament')
def load_filament():
    modt.load_filament()
    return jsonify()


@printer.route('/unload-filament')
def unload_filament():
    modt.unload_filament()
    return jsonify()

