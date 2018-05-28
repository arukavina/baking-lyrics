from api.v1.models.machine_learning import TitleLSTMModel
from flask import current_app


class ModelsManager():
    def __init__(self):
        return

    def get_model(self, key):
        model = TitleLSTMModel(current_app.config["TITLE_LSTM_MODEL_FILE_PATH"])
        model.load_model()
        return model

