from flask import Flask
from modtpy.api.errors import PrinterError
from modtpy.web.errors import handle_error
from modtpy.web.main.controllers import main
from modtpy.web.printer.controllers import printer

server = Flask(__name__)
server.errorhandler(PrinterError)(handle_error)
server.register_blueprint(main, url_prefix='/')
server.register_blueprint(printer, url_prefix='/printer')