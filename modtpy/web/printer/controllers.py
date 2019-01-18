from flask import Blueprint, jsonify
from modtpy.api.modt import ModT, Mode

printer = Blueprint('printer', __name__)


@printer.before_request
def before_request():
    if not hasattr(printer, 'modt'):
        printer.modt = ModT()
        printer.modt.run_status_loop()
    

@printer.route('/status')
def status():
    mode = Mode.to_string(printer.modt.mode)
    status = printer.modt.get_status()
    return jsonify(mode=mode, status=status)


@printer.route('/load-filament')
def load_filament():
    printer.modt.load_filament()
    return jsonify()


@printer.route('/unload-filament')
def unload_filament():
    printer.modt.unload_filament()
    return jsonify()

