from flask import Flask, jsonify
import pickle
import json

class ErrorHandler:
    """Class for managing errors"""

    def __init__(self, code, message):
        #constructor
        self.code = code
        self.message = message

    def return_json_error(self):
        #return a json with the object structure
        d = {'status': self.code, 'message': str(self.message)}
        return jsonify(d)