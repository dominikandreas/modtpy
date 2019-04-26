import json
import traceback
import logging


def parse_json(msg, handle_exception=True):
    json_res = dict(str=msg)
    try:
        json_res.update(json.loads(msg))
    except Exception as e:
        if handle_exception:
            logging.exception("Exception occurred during json parsing")
            tb = traceback.format_exc()
            json_res["_exc"] = str(e) + "\n" + msg(tb)
        else:
            raise e
    return json_res
