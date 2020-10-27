from io import BytesIO
import time
from pathlib import Path
import traceback
from flask import Blueprint, jsonify, request

from modtpy.api.gcode_optimization import GcodeOptimizer
from modtpy.api.modt import ModT, Mode
import logging
from queue import LifoQueue


printer = Blueprint('printer', __name__)


class WebLoggingHandler(logging.Handler):
    max_size = 25
    queue = LifoQueue()

    def emit(self, record):
        msg = self.format(record)
        if "GET /" not in msg and "POST /" not in msg:
            messages = self.queue.get() if self.queue.qsize() else []
            for line in msg.split("\n"):
                line = line.replace("\t", "  ")
                t = time.time()
                messages.append(dict(time_fmt=time.strftime("%H:%M:%S"),
                                     timestamp=t,
                                     id=str(t) + str(hash(line))[:5],
                                     message=line.replace("\t", "  ")))
            self.queue.put(messages[-self.max_size:])

    @classmethod
    def get_messages(cls):
        if cls.queue.qsize():
            messages = cls.queue.get()
            cls.queue.put(messages)
            return messages
        else:
            return []


level = logging.INFO
h = WebLoggingHandler()
root = logging.getLogger()
root.addHandler(h)
root.setLevel(level)


modt = ModT()
modt.run_status_loop()


@printer.route('/set-log-level', methods=["POST"])
def set_log_level():
    level_str = request.args.get("level")
    loglevel = getattr(logging, level_str.upper())
    root.setLevel(loglevel)


def handle_exception(function):
    def __wrapper__(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:
            logging.warning(f"Exception occurred while executing %s: %s", function.__name__, e)
            tb = traceback.format_exc()
            print(tb)
            logging.debug(tb)
            return jsonify(error=str(e))

    __wrapper__.__name__ = function.__name__
    return __wrapper__


@printer.route('/status')
@handle_exception
def status():
    try:
        mode = Mode.to_string(modt.mode)
    except Exception as e:
        logging.exception("unable to get mode")
        mode = dict(error=str(e))
    try:
        status_dict = modt.get_status()
    except Exception as e:
        logging.exception("unable to get status")
        status_dict = dict(error=str(e))

    logs = WebLoggingHandler.get_messages()
    return jsonify(mode=mode, status=status_dict, logs=logs)


@printer.route('/upload-gcode', methods=["POST"])
@handle_exception
def upload_gcode():
    file = next(iter(request.files.values()))
    should_optimize = request.values.get("optimize") == "true"

    extension = Path(file.filename).suffix
    if extension.lower() != ".gcode":
        raise RuntimeError("only gcode extensions supported but got " + extension)

    if should_optimize:
        gcode = file.stream.read().decode("utf-8")
        optimized = GcodeOptimizer().optimize_gcode(gcode, logger=root)
        file.stream = BytesIO()
        file.stream.write(optimized.encode())
        file.stream.seek(0)

    modt.send_gcode(file.stream, logger=root)
    modt.press_button()
    return status()


@printer.route('/load-filament')
@handle_exception
def load_filament():
    modt.load_filament()
    return status()


@printer.route('/unload-filament')
@handle_exception
def unload_filament():
    modt.unload_filament()
    return status()
