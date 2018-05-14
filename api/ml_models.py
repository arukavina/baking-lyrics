#!/usr/bin/env python
"""
Modeling Classes
"""

# Generic
import abc
import os
import datetime

# Own
from api.util import log_utils

logger = log_utils.get_logger('api')


class Model(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(self, model_file_path):

        logger.info('Checking if "model" is a valid path: {}'.format(model_file_path))
        if not os.path.exists(model_file_path):
            logger.error("[{}] is not a valid path".format(model_file_path))
            raise IOError()

        self.model_file_path = model_file_path
        self.model = None
        self.model_loaded = False

        super().__init__()
        pass

    @abc.abstractmethod
    def load_model(self):
        raise NotImplementedError('User must define load_model to use this base class')

    @abc.abstractmethod
    def __str__(self):
        raise NotImplementedError('User must define __str__ to use this base class')

    @abc.abstractmethod
    def generate_sentence(self, *kargs):
        raise NotImplementedError('User must define generate_sentence to use this base class')


class NGramsModel(Model):
    def __init__(self, model_file_path, seed_file_path="../data/corpus.txt"):

        logger.info('Checking if "seed_file_path" is a valid path: {}'.format(seed_file_path))
        if not os.path.exists(seed_file_path):
            logger.error("[{}] is not a valid path".format(seed_file_path))
            raise IOError()

        super().__init__(model_file_path)

        self.seed_file_path = seed_file_path

        self.text = None
        self.characters = None
        self.length = None

    def load_model(self):

        self.text = (open(self.seed_file_path).read())
        self.text = self.text.lower().strip()
        self.characters = sorted(list(set(self.text)))
        self.length = len(self.text)

        logger.info("Characters V: {}".format(self.characters))
        logger.info("Text length: {}".format(self.length))

        # TODO: Complete this method.
        loaded_model = None

        self.model = loaded_model
        self.model_loaded = True

        logger.info("Loaded model from disk")

    def generate_sentence(self, lang='es', length=100, seed=69, *kargs):

        if lang != 'es':
            raise NotImplementedError

        if not self.model_loaded:
            logger.info("Model not loaded, loading it now...")
            self.load_model()

        # TODO: Complete this method.
        txt = ""

        logger.info('Generated: {}'.format(txt))

        return txt

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))


class LyricsLSTMModel(Model):
    def __init__(self, model_file_path, weights_file_path, seed_file_path="../data/martin-fierro.txt"):

        logger.info('Checking if "weights_file_path" is a valid path: {}'.format(weights_file_path))
        if not os.path.exists(weights_file_path):
            logger.error("[{}] is not a valid path".format(weights_file_path))
            raise IOError()

        logger.info('Checking if "seed_file_path" is a valid path: {}'.format(seed_file_path))
        if not os.path.exists(seed_file_path):
            logger.error("[{}] is not a valid path".format(seed_file_path))
            raise IOError()

        super().__init__(model_file_path)

        self.weights_file_path = weights_file_path
        self.seed_file_path = seed_file_path

        self.text = None
        self.characters = None
        self.length = None

    def load_model(self):
        from keras.models import model_from_yaml

        self.text = (open(self.seed_file_path).read())
        self.text = self.text.lower().strip()
        self.characters = sorted(list(set(self.text)))
        self.length = len(self.text)

        logger.info("Characters V: {}".format(self.characters))
        logger.info("Text length: {}".format(self.length))

        # Load YAML and create model
        logger.info("Loading model...")

        try:
            yaml_file = open(self.model_file_path, 'r')
            loaded_model_yaml = yaml_file.read()
            yaml_file.close()

            loaded_model = model_from_yaml(loaded_model_yaml)
        except IOError as e:
            logger.error("Is not possible to load Keras model")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        # Load weights into new model
        logger.info("Loading weights into new model...")

        try:
            loaded_model.load_weights(self.weights_file_path)
        except IOError as e:
            logger.error("Is not possible to load weights into Keras model")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        self.model = loaded_model
        self.model_loaded = True
        logger.info("Loaded model from disk")

    def generate_sentence(self, lang='es', length=100, seed=69, *kargs):

        import numpy as np
        from keras.utils import np_utils

        if lang != 'es':
            raise NotImplementedError

        if not self.model_loaded:
            logger.info("Model not loaded, loading it now...")
            self.load_model()

        X = []
        Y = []

        seq_length = 100

        for i in range(0, self.length - seq_length, 1):
            sequence = self.text[i:i + seq_length]
            label = self.text[i + seq_length]
            X.append([self.char_to_n()[char] for char in sequence])
            Y.append(self.char_to_n()[label])

            logger.debug(label, '->', Y[i])

        X_modified = np.reshape(X, (len(X), seq_length, 1))
        X_modified = X_modified / float(len(self.characters))
        Y_modified = np_utils.to_categorical(Y)

        # Generating Text

        string_mapped = X[seed]

        logger.info(string_mapped)

        full_string = [self.n_to_char()[value] for value in string_mapped]

        g_txt = ''
        for char in full_string:
            g_txt = g_txt + char

        logger.info('Base: \n{}'.format(g_txt))

        full_string = []

        # Generating N characters

        for i in range(length):
            x = np.reshape(string_mapped, (1, len(string_mapped), 1))

            x = x / float(len(self.characters))

            pred_index = int(np.argmax(self.model.predict(x, verbose=0)))

            logger.debug(pred_index, '->', self.n_to_char()[pred_index])

            seq = [self.n_to_char()[value] for value in string_mapped]

            full_string.append(self.n_to_char()[pred_index])

            string_mapped.append(pred_index)
            string_mapped = string_mapped[1:len(string_mapped)]

        # Merging results
        g_txt = ''
        for char in full_string:
            g_txt = g_txt + char

        logger.info('Generated: {}'.format(g_txt))

        return g_txt

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))

    def n_to_char(self):
        return {n: char for n, char in enumerate(self.characters)}

    def char_to_n(self):
        return {char: n for n, char in enumerate(self.characters)}


class TitleLSTMModel(Model):
    def __init__(self, model_file_path, tokenizer_file_path):

        logger.info('Checking if "tokenizer_file_path" is a valid path: {}'.format(tokenizer_file_path))
        if not os.path.exists(tokenizer_file_path):
            logger.error("[{}] is not a valid path".format(tokenizer_file_path))
            raise IOError()

        super().__init__(model_file_path)

        self.tokenizer_file_path = tokenizer_file_path

        self.text = None
        self.characters = None
        self.length = None

    def load_model(self):

        self.text = self.text.lower().strip()
        self.characters = sorted(list(set(self.text)))
        self.length = len(self.text)

        logger.info("Characters V: {}".format(self.characters))
        logger.info("Text length: {}".format(self.length))

        # Load YAML and create model
        logger.info("Loading model...")

        # TODO: Sergio.

        self.model = None
        self.model_loaded = True
        logger.info("Loaded model from disk")

    def generate_sentence(self, lang='es', length=100, seed=69, *kargs):

        g_txt = range(1, length)
        return g_txt

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))


if __name__ == '__main__':

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

    settings = dict(
        log_dir=r'../logs',
        log_level=2
    )

    log_utils.setup_logging('bl-api-mlAbl', timestamp, settings)
    logger = log_utils.get_logger('bl-api-mlAbl')

    logger.info(os.getcwd())

    a = LyricsLSTMModel(
        model_file_path='../resources/text_generator_dummy.yaml',
        weights_file_path='../resources/text_generator_dummy_weights.h5'
    )

    txt = a.generate_sentence(length=50, seed=69)
    # a.__str__()
