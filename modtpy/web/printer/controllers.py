from flask import Blueprint, jsonify, g
from modtpy.web.errors import USBError
import usb.core
from modtpy.api import ModT

printer = Blueprint('printer', __name__)

@printer.before_request
def before_request():
    if hasattr(g, 'modt'):
        return
    try:
        g.modt = ModT()
        g.modt.dev # TODO: some better way to check connectivity upfront
    except (ValueError, usb.core.NoBackendError) as error:
        raise USBError(str(error), status_code=503)

@printer.route('/status')
def status():
    status = g.modt.get_status()
    return jsonify(status=status)

@printer.route('/load-filament')
def load_filament():
    g.modt.load_filament()
    return jsonify()

@printer.route('/unload-filament')
def unload_filament():
    g.modt.unload_filament()
    return jsonify()

