#!/usr/bin/env python
"""
Modeling Classes
"""

# Generic
import abc
import os
import datetime

# Libs
import numpy as np
import pickle

# Own
from baking.main.util import log_utils

logger = log_utils.get_logger('baking-api')


class Model(object, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def __init__(self, model_file_path):
        """
        ABC Model class. Instantiates with the model file path
        :param model_file_path: path to model
        """

        logger.info('Checking if "model_file_path" is a valid path: {}'.format(model_file_path))
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
        """

        :param model_file_path:
        :param seed_file_path:
        """

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
        """
        Opens and loads model specific files imn memory
        :return: None
        """

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

        logger.info("Models loaded from disk successfully")

    def generate_sentence(self, lang='es', length=100, seed=69, *kargs):
        """
        Generates Sentes for current model
        :param lang: By default: en
        :param length: Size of words array to generate
        :param seed: Seed to use
        :param kargs: Other model specific *kargs
        :return:
        """

        if lang != 'en':
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


class Glove(Model):
    def __init__(self, glove_binary_path):
        """

        :param glove_binary_path:
        """

        super().__init__(glove_binary_path)

        self.glove_binary_path = glove_binary_path

    def load_model(self):
        """
        Opens and loads model specific files in memory
        :return: None
        """

        logger.info('Indexing word vectors.')

        embeddings_index = {}
        with open(self.glove_binary_path) as f:
            for line in f:
                values = line.split()
                word = values[0]
                coefficients = np.asarray(values[1:], dtype='float32')
                embeddings_index[word] = coefficients

        logger.info('Found %s word vectors.' % len(embeddings_index))
        logger.info('Models loaded from disk successfully')

        self.model = embeddings_index
        self.model_loaded = True

    def generate_sentence(self, *kargs):
        """

        :param kargs:
        :return:
        """
        raise NotImplementedError

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))


class LyricsSkthModel(Model):

    def __init__(self,
                 decoder_model_path,
                 gen_model_context_path,
                 model_verse_emb_context_path,
                 model_stv_encoder_path,
                 tokenizer):

        """

        :param decoder_model_path:
        :param gen_model_context_path:
        :param model_verse_emb_context_path:
        :param model_stv_encoder_path:
        :param tokenizer:
        """

        logger.info('Checking if "generator_model_context_path" is a valid path: {}'.format(gen_model_context_path))
        if not os.path.exists(gen_model_context_path):
            logger.error("[{}] is not a valid path".format(gen_model_context_path))
            raise IOError()

        logger.info('Checking if "model_verse_emb_context_path" is a valid path: {}'.format(
            model_verse_emb_context_path)
        )
        if not os.path.exists(model_verse_emb_context_path):
            logger.error("[{}] is not a valid path".format(model_verse_emb_context_path))
            raise IOError()

        logger.info('Checking if "model_stv_encoder_path" is a valid path: {}'.format(model_stv_encoder_path))
        if not os.path.exists(model_stv_encoder_path):
            logger.error("[{}] is not a valid path".format(model_stv_encoder_path))
            raise IOError()

        if tokenizer is None:
            raise AttributeError()
        else:
            self.t = tokenizer

        super().__init__(decoder_model_path)

        self.decoder_model_path = decoder_model_path
        self.generator_model_context_path = gen_model_context_path
        self.model_verse_emb_context_path = model_verse_emb_context_path
        self.model_stv_encoder_path = model_stv_encoder_path

        self.max_verse_length = 20
        self.max_number_verses = 40

        self.text = None
        self.characters = None
        self.length = None
        
        # Model Parameters
        self.latent_dim = 0
        self.max_song_length = 100
        
        # Model Binaries
        # TODO: Define load for all this

        self.decoder_model = None
        self.generator_model_context = None
        self.model_verse_emb_context = None
        self.model_stv_encoder = None

    def load_model(self):
        """

        :return:
        """

        # Keras Imports
        from keras.models import model_from_yaml

        # Load YAML and create models
        logger.info("Loading models...")

        try:
            yaml_file = open(self.model_file_path, 'r')
            loaded_model_yaml = yaml_file.read()
            yaml_file.close()

            loaded_model = model_from_yaml(loaded_model_yaml)
        except IOError as e:
            logger.error("Is not possible to load Keras models")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        self.model = loaded_model
        self.model_loaded = True
        logger.info("Loaded models from disk")

    def generate_sentence(self,
                          encoded_vector_title,
                          encoded_vector_song_mean,
                          artist_token,
                          genre_token,
                          lang='en',
                          length=100,
                          random_seed=69,
                          num_generated=128,
                          max_length=None,
                          temperature=0.6,
                          depth_search_replace=5,
                          width_search_replace=64,
                          batch_size=None):
        """

        :param encoded_vector_title:
        :param encoded_vector_song_mean:
        :param artist_token:
        :param genre_token:
        :param lang:
        :param length:
        :param random_seed:
        :param num_generated:
        :param max_length:
        :param temperature:
        :param depth_search_replace:
        :param width_search_replace:
        :param batch_size:
        :return:
        """
        # Keras Imports
        from keras.preprocessing.sequence import pad_sequences

        if max_length is None:
            max_length = self.max_song_length - 1

        if lang != 'en':
            raise NotImplementedError

        if not self.model_loaded:
            logger.info("Model not loaded, loading it now...")
            self.load_model()

        if batch_size is None:
            batch_size = num_generated

        context = self.generator_model_context.predict(
            [encoded_vector_title, encoded_vector_song_mean, artist_token, genre_token]
        )

        context = np.repeat(context, num_generated, axis=0)

        # First verse skip-thought vector

        state_h_1 = np.zeros((num_generated, self.latent_dim * 5))
        state_c_1 = np.zeros((num_generated, self.latent_dim * 5))
        state_h_2 = np.zeros((num_generated, self.latent_dim * 5))
        state_c_2 = np.zeros((num_generated, self.latent_dim * 5))

        z = np.zeros((1, self.latent_dim * 5))

        encoded_vector, sh1, sc1, sh2, sc2 = self.model_verse_emb_context.predict([np.zeros((1, 1, self.latent_dim)),
                                                                                   encoded_vector_title,
                                                                                   encoded_vector_song_mean,
                                                                                   artist_token, genre_token,
                                                                                   z, z, z, z])
        encoded_vector = encoded_vector[0, 0, :]
        encoded_vector = np.tile(encoded_vector, (self.max_song_length, 1))
        encoded_vector = encoded_vector.reshape((1, encoded_vector.shape[0], encoded_vector.shape[1]))
        encoded_vector = np.repeat(encoded_vector, num_generated, axis=0)

        state_h_1[:, :] = sh1
        state_c_1[:, :] = sc1
        state_h_2[:, :] = sh2
        state_c_2[:, :] = sc2

        # Place holder variables
        sequence = self.t.tokenizer.texts_to_sequences(['xseqstart'])
        sequence = pad_sequences(sequence, padding='post', truncating='post', maxlen=self.max_song_length)
        sequence = np.repeat(sequence, num_generated, axis=0)
        score = np.zeros(num_generated)
        verse_n = np.zeros(num_generated, dtype=int)
        state_h = np.zeros((num_generated, self.latent_dim * 2))
        state_c = np.zeros((num_generated, self.latent_dim * 2))
        verse_indexes = np.zeros(num_generated, dtype=int)
        verse_sequences = np.zeros((num_generated, self.max_verse_length))
        verse_sequences[:, 0] = self.t.tokenizer.word_index['xseqstart']
        encoded_verses_matrix = np.zeros((num_generated, self.max_number_verses, self.latent_dim))

        for j in range(max_length - 1):
            if (j + 1) % depth_search_replace == 0:
                worst = np.argsort(score) < width_search_replace
                best = np.argsort(-score) < width_search_replace
                sequence[worst] = sequence[best]
                score[worst] = score[best]

                verse_n[worst] = verse_n[best]
                state_h[worst] = state_h[best]
                state_c[worst] = state_c[best]
                encoded_vector[worst] = encoded_vector[best]

                state_h_1[worst] = state_h_1[best]
                state_c_1[worst] = state_c_1[best]
                state_h_2[worst] = state_h_2[best]
                state_c_2[worst] = state_c_2[best]

            print(j, end=' ')
            sequence_current = sequence[:, j].reshape((num_generated, 1))
            encoded_vector_current = encoded_vector[:, j, :].reshape((num_generated, 1, encoded_vector.shape[2]))

            prediction, state_h, state_c = self.decoder_model.predict([sequence_current,
                                                                       encoded_vector_current,
                                                                       context,
                                                                       state_h,
                                                                       state_c], batch_size=batch_size)

            idx, logp, p_end, p_newline_feed = sample(prediction[:, 0, :], temperature=temperature)

            # no end hardcoded
            idx = np.array([self.t.tokenizer.word_index['xnewlinefeed']
                            if self.t.reverse_word_map.get(x, '') == 'xseqend'
                            else x
                            for x in idx])

            score += logp
            sequence[:, j + 1] = idx

            # i 0 1 2 3 4
            # v s p e p e
            # j   0 1 2 3

            mask = idx == self.t.tokenizer.word_index['xnewlinefeed']
            num_new_verses = np.sum(mask)
            if num_new_verses > 0:

                for s in np.arange(num_generated)[mask]:
                    v_len = min(int(j - verse_indexes[s]), self.max_verse_length - 2)

                    verse_sequences[s, 1:(v_len + 1)] = sequence[
                                                        s,
                                                        (verse_indexes[s] + 1):(verse_indexes[s] + v_len + 1)
                                                        ]
                    verse_sequences[s, v_len + 1] = self.t.tokenizer.word_index['xseqend']
                    verse_sequences[s, min(v_len + 2, self.max_verse_length - 1):] = 0

                encoded_verses = self.model_stv_encoder.predict(verse_sequences[mask], batch_size=batch_size)
                encoded_verses_matrix[np.arange(num_generated), verse_n][mask] = encoded_verses

                new_emb, state_h_1[mask], state_c_1[mask], state_h_2[mask], state_c_2[
                    mask] = self.model_verse_emb_context.predict(
                    [encoded_verses.reshape(encoded_verses.shape[0], 1, encoded_verses.shape[1]),
                     np.repeat(encoded_vector_title, num_new_verses, axis=0),
                     np.repeat(encoded_vector_song_mean, num_new_verses, axis=0),
                     np.repeat(artist_token, num_new_verses, axis=0),
                     np.repeat(genre_token, num_new_verses, axis=0),
                     state_h_1[mask], state_c_1[mask], state_h_2[mask], state_c_2[mask]],
                    batch_size=batch_size)

                encoded_verses_matrix[mask, verse_n[mask]] = new_emb.reshape(new_emb.shape[0], new_emb.shape[2])
                encoded_vector[mask, (j + 1):(self.max_song_length - 1)] = new_emb

                verse_indexes[mask] = j + 1

        logger.info('Generated: {}'.format(''))

        return sequence, [text_from_sequence(s) for s in sequence], score

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))


class LyricsLSTMModel(Model):

    def __init__(self, model_file_path, weights_file_path, seed_file_path="../data/martin-fierro.txt"):
        """
        :param model_file_path:
        :param weights_file_path:
        :param seed_file_path:
        """

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
        """
        :return:
        """
        from keras.models import model_from_yaml

        self.text = (open(self.seed_file_path).read())
        self.text = self.text.lower().strip()
        self.characters = sorted(list(set(self.text)))
        self.length = len(self.text)

        logger.info("Characters V: {}".format(self.characters))
        logger.info("Text length: {}".format(self.length))

        # Load YAML and create models
        logger.info("Loading models...")

        try:
            yaml_file = open(self.model_file_path, 'r')
            loaded_model_yaml = yaml_file.read()
            yaml_file.close()

            loaded_model = model_from_yaml(loaded_model_yaml)
        except IOError as e:
            logger.error("Is not possible to load Keras models")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        # Load weights into new models
        logger.info("Loading weights into new models...")

        try:
            loaded_model.load_weights(self.weights_file_path)
        except IOError as e:
            logger.error("Is not possible to load weights into Keras models")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        self.model = loaded_model
        self.model_loaded = True
        logger.info("Loaded models from disk")

    def generate_sentence(self, lang='es', length=100, seed=69, *kargs):
        """
        :param lang:
        :param length:
        :param seed:
        :param kargs:
        :return:
        """

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

    def __init__(self, model_file_path):
        """
        :param model_file_path:
        """
        super().__init__(model_file_path)
        self.tokenizer = None

    def load_model(self):
        """
        :return:
        """
        from keras.models import load_model
        import pickle

        logger.info("Loading model...")
        try:
            loaded_model = load_model(self.model_file_path + '.h5')
        except IOError as e:
            logger.error("Is not possible to load Keras model")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        logger.info("Tokenizer model...")
        try:
            with open(self.model_file_path + '.tokenizer.pickle', 'rb') as handle:
                tokenizer = pickle.load(handle)

        except IOError as e:
            logger.error("Is not possible to load tokenizer")
            raise e
        except ImportError as e:
            logger.error("Missing dependency")
            raise e

        self.model = loaded_model
        self.tokenizer = tokenizer
        self.model_loaded = True
        logger.info("Loaded model from disk")

    def generate_sentence(self, input_text='', temperature=0., max_output_sequence_lenght=8, number_of_titles=3, *kargs):
        """
        :param input_text:
        :param temperature:
        :param max_output_sequence_lenght:
        :param number_of_titles:
        :param kargs:
        :return:
        """
        import numpy as np
        from keras.preprocessing.sequence import pad_sequences

        reverse_word_map = dict(map(reversed, self.tokenizer.word_index.items()))

        input_text = input_text.lower().replace("'", ' ').replace('\n', 'xnewline ')
        input_sequence = self.tokenizer.texts_to_sequences([input_text])
        input_sequence = pad_sequences(input_sequence, padding='post', truncating='post', maxlen=100)

        start_token_value = self.tokenizer.texts_to_sequences(['xseqstart'])[0][0]
        end_token_value = self.tokenizer.texts_to_sequences(['xseqend'])[0][0]
        output_sequence = np.zeros((1, max_output_sequence_lenght), dtype=int)
        output_sequence[0, 0] = start_token_value

        titles = []
        for j in range(number_of_titles):
            output_sequence = np.zeros((1, max_output_sequence_lenght), dtype=int)
            pred_sequence = np.zeros((1, max_output_sequence_lenght), dtype=int)
            output_sequence[0, 0] = start_token_value

            for i in range(max_output_sequence_lenght):
                output_tokens = self.model.predict([input_sequence, output_sequence])
                output_tokens = output_tokens + np.random.normal(size=output_tokens.shape)*temperature
                pred_sequence[0,] = [np.argsort(output_tokens[0, ii])[(-1 - max(j - ii * 10, 0))] for ii in
                                     range(max_output_sequence_lenght)]

                for ii in range(max_output_sequence_lenght - 1):
                    output_sequence[0, ii + 1] = pred_sequence[0, ii]

            clean_output_sequence = filter(lambda x: x not in set([start_token_value, end_token_value, 0]),
                                           output_sequence[0])
            titles.append(" ".join([reverse_word_map.get(token, '') for token in clean_output_sequence]))

        return titles[0]

    def __str__(self):
        from pprint import pprint
        pprint(vars(self))


def sample(preds_p, tokenizer, temperature=1.0):
    if temperature <= 0:
        return np.argmax(preds_p)

    preds_p[:, tokenizer.word_index[5001]] = 0.000000000000001  # delete the unknown!

    preds = np.asarray(preds_p).astype('float64')
    preds = np.log(preds) / temperature
    exp_preds = np.exp(preds)
    preds = exp_preds / np.sum(exp_preds, axis=1, keepdims=True)

    probas = np.concatenate([np.random.multinomial(1, x, 1) for x in preds])

    idx = np.argmax(probas, axis=1)

    return idx, np.log(preds_p[range(len(idx)), idx]), preds_p[:, tokenizer.word_index['xseqend']], preds_p[:, tokenizer.word_index['xnewlinefeed']]


def text_pre_process(text):

    text = str(text)\
        .lower()\
        .replace(',', ' ,')\
        .replace(".", ' .')\
        .replace("?", ' ?')\
        .replace("!", ' !')\
        .replace('\n',  ' xnewlinefeed ')\
        .replace('\t', ' ')\
        .replace("'", " '")\
        .replace('"', '')\
        .replace("(", '')\
        .replace(")", '')\
        .replace("-", '')\
        .replace('  ', ' ')

    return 'xseqstart ' + text.strip() + ' xseqend'


def text_from_sequence(sequence, reverse_word_map):
    return " ".join([str(reverse_word_map.get(token, '')) for token in sequence])


def encode_verse(verse, tokenizer, model_stv_encoder, max_verse_length=20):

    from keras.preprocessing.sequence import pad_sequences

    input_sequence = tokenizer.texts_to_sequences([verse])
    input_sequence = pad_sequences(input_sequence, padding='post', truncating='post', maxlen=max_verse_length)
    encoded_vector = model_stv_encoder.predict(input_sequence)[0].T
    return encoded_vector.reshape((1, encoded_vector.shape[0]))


class Tokenizer:

    def __init__(self, model_name, artist_genre_tokenizer_path, tokenizer_path, embedded_matrix_path):
        """

        :param model_name:
        :param artist_genre_tokenizer_path:
        :param tokenizer_path:
        :param embedded_matrix_path:
        """

        if model_name is None:
            raise AttributeError('model_name can\'t be None')

        logger.info('Checking if "artist_genre_tokenizer_path" is a valid path: {}'.format(artist_genre_tokenizer_path))
        if not os.path.exists(artist_genre_tokenizer_path):
            logger.error("[{}] is not a valid path".format(artist_genre_tokenizer_path))
            raise IOError()

        logger.info('Checking if "tokenizer_path" is a valid path: {}'.format(tokenizer_path))
        if not os.path.exists(tokenizer_path):
            logger.error("[{}] is not a valid path".format(tokenizer_path))
            raise IOError()

        logger.info('Checking if "embedded_matrix_path" is a valid path: {}'.format(embedded_matrix_path))
        if not os.path.exists(embedded_matrix_path):
            logger.error("[{}] is not a valid path".format(embedded_matrix_path))
            raise IOError()

        self.model_name = model_name
        self.artist_genre_tokenizer_path = artist_genre_tokenizer_path
        self.tokenizer_path = tokenizer_path
        self.embedded_matrix_path = embedded_matrix_path

        self.embedding_matrix = None
        self.genre_tokenizer = None
        self.artist_tokenizer = None
        self.reverse_word_map = None

        self.tokenizer = None

    @property
    def embedding_matrix(self):
        return self.embedding_matrix

    @embedding_matrix.setter
    def embedding_matrix(self, value):
        self.embedding_matrix = value

    @property
    def genre_tokenizer(self):
        return self.genre_tokenizer

    @genre_tokenizer.setter
    def genre_tokenizer(self, value):
        self.genre_tokenizer = value

    @property
    def artist_tokenizer(self):
        return self.artist_tokenizer

    @artist_tokenizer.setter
    def artist_tokenizer(self, value):
        self.artist_tokenizer = value

    @property
    def reverse_word_map(self):
        return self.reverse_word_map

    @reverse_word_map.setter
    def reverse_word_map(self, value):
        self.reverse_word_map = value

    @property
    def tokenizer(self):
        return self.tokenizer

    @tokenizer.setter
    def tokenizer(self, value):
        self.tokenizer = value

    def load(self):
        """
        Opens and loads model specific files imn memory
        :return: None
        """
        logger.info('Loading tokenizers')

        agt = np.load(self.artist_genre_tokenizer_path)
        self.genre_tokenizer = agt['genre_tokenizer'].tolist()
        self.artist_tokenizer = agt['artist_tokenizer'].tolist()

        self.embedding_matrix = np.load(self.embedded_matrix_path)['embedding_matrix']

        with open(self.tokenizer_path, 'rb') as handle:
            self.tokenizer = pickle.load(handle)

        self.reverse_word_map = dict(map(reversed, self.tokenizer.word_index.items()))

        logger.info("Tokenizers loaded from disk successfully")


if __name__ == '__main__':

    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M_%S')

    settings = dict(
        log_dir=r'../logs',
        log_level=2
    )

    log_utils.setup_logging('bl-api-mlAbl', timestamp, settings)
    logger = log_utils.get_logger('bl-api-mlAbl')

    logger.info(os.getcwd())

    model_name_str = 'lyrics_skth_v0_20_40_300_5000_100'

    # Loading Tokenizer

    tokenizer_filename = os.path.join(model_name_str, '.tokenizer.pickle')
    embedding_matrix_filename = os.path.join(model_name_str, '.embmat.npz')
    artist_genre_tokenizer_filename = os.path.join(model_name_str, '.artist_genre_tokenizer.npz')

    t = Tokenizer(model_name=model_name_str,
                  artist_genre_tokenizer_path=artist_genre_tokenizer_filename,
                  tokenizer_path=tokenizer_filename,
                  embedded_matrix_path=embedding_matrix_filename)
    t.load()

    a = LyricsSkthModel(
        decoder_model_path='../resources/models/decoder.h5',
        gen_model_context_path='../resources/models/generator_model_context.h5',
        model_verse_emb_context_path='../resources/models/verse_emb_context.h5',
        model_stv_encoder_path='../resources/models/stv_encoder.h5',
        tokenizer=t
    )

    title = 'xseqstart working class xseqend'
    input_texts = ['xseqstart flower grows in texas xseqend',
                   'xseqstart nick works in texas xseqend',
                   'xseqstart texas is my country xseqend']
    artist = 'blake-shelton'
    genre = 'Country'

    encoded_vector_title = encode_verse(title, tokenizer=t.tokenizer,
                                        model_stv_encoder=model_stv_encoder,  # From a object
                                        max_verse_length=20)
    encoded_vector_song_mean = np.mean([encode_verse(x) for x in input_texts], axis=0)
    artist_token = np.array(t.artist_tokenizer[artist]).reshape((1, 1))
    genre_token = np.array(t.genre_tokenizer[genre]).reshape((1, 1))

    results = a.generate_sentence(generator_model_word,  # From self
                                  encoded_vector_title,
                                  encoded_vector_song_mean,
                                  artist_token,
                                  genre_token,
                                  num_generated=128*2,
                                  max_length=128,
                                  temperature=0.7,
                                  depth_search_replace=5,
                                  width_search_replace=128,
                                  length=50,
                                  random_seed=69)
    # a.__str__()
