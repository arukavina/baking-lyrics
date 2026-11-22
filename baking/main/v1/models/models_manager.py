from flask import current_app

from baking.main.v1.models.machine_learning import TitleLSTMModel


class ModelsManager:
    def __init__(self):
        if hasattr(current_app, 'models_cache'):
            self.models_cache = current_app.models_cache
        else:
            self.models_cache = dict()
            current_app.models_cache = self.models_cache
        return

    def get_model(self, key):
        """

        :param key:
        :return: Model to be used. It could be directly from cache
        """
        if key not in self.models_cache:
            if key == 'titles':
                from baking.main import resolve_path

                model = TitleLSTMModel(str(resolve_path(current_app.config["TITLE_LSTM_MODEL_FILE_PATH"])))
                model.load_model()
                self.models_cache[key] = model
            else:
                raise ValueError(f'Unknown model key: {key}')
        return self.models_cache[key]
