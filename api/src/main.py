from flask import Flask, jsonify
from flask import abort
from src.helpers import ErrorHandler as Eh
from werkzeug.exceptions import HTTPException

app = Flask(__name__)


@app.route('/api/eg/<int:eg_id>', methods=['GET'])
def get_tasks(eg_id):
    try:
        if(eg_id == 0):
            abort(404,"problem")
        return "get example: " + str(eg_id)
    except HTTPException:
        raise
    except Exception as e:
       abort(505, "Unexpected error")



#Base HTTP Errors handler
@app.errorhandler(404)
def not_found(error):
    error_object = Eh.ErrorHandler(404, error)
    return error_object.return_json_error()

@app.errorhandler(505)
def not_found(error):
    error_object = Eh.ErrorHandler(505, error)
    return error_object.return_json_error()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)