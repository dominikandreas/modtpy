from flask import jsonify

def handle_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response