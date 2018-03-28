#!/usr/bin/env python
"""
RNN Keras Model Factory.
"""

# Generic
import datetime
import os

# Libs
import numpy as np
import pandas as pd

# Keras
from keras.layers import Dense
from keras.layers import Dropout
from keras.layers import LSTM
from keras.models import Sequential
from keras.utils import np_utils
from keras.models import model_from_yaml

# Own
from util import log_utils
from util import settings_util


text = (open("../../../data/martin-fierro.txt").read())
text = text.lower().strip()

characters = sorted(list(set(text)))
n_to_char = {n: char for n, char in enumerate(characters)}
char_to_n = {char: n for n, char in enumerate(characters)}

X = []
Y = []
length = len(text)

print(text[100])
print(length)

seq_length = 100

for i in range(0, length - seq_length, 1):
    sequence = text[i:i + seq_length]
    label = text[i + seq_length]
    X.append([char_to_n[char] for char in sequence])
    Y.append(char_to_n[label])

X_modified = np.reshape(X, (len(X), seq_length, 1))
X_modified = X_modified / float(len(characters))
Y_modified = np_utils.to_categorical(Y)

print(X_modified[1])

big = False

if big:
    model = Sequential()
    model.add(LSTM(700, input_shape=(X_modified.shape[1], X_modified.shape[2]), return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(700, return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(700))
    model.add(Dropout(0.2))
    model.add(Dense(Y_modified.shape[1], activation='softmax'))
    model.compile(loss='categorical_crossentropy', optimizer='adam')
    model_name = 'text_generator_700_0.2_700_0.2_700_0.2_100_big'

else:
    model = Sequential()
    model.add(LSTM(400, input_shape=(X_modified.shape[1], X_modified.shape[2]), return_sequences=True))
    model.add(Dropout(0.2))
    model.add(LSTM(400))
    model.add(Dropout(0.2))
    model.add(Dense(Y_modified.shape[1], activation='softmax'))
    model.compile(loss='categorical_crossentropy', optimizer='adam')
    model_name = 'text_generator_400_0.2_400_0.2_100_small'


# Good sizes are: 100 epochs and 50 batch size
model.fit(X_modified, Y_modified, epochs=100, batch_size=50)

# Saving Model

# Serialize model to YAML

model_yaml = model.to_yaml()
with open("../../../models/{}_model.yaml".format(model_name), "w") as yaml_file:
    yaml_file.write(model_yaml)
# serialize weights to HDF5
model.save_weights('../../../models/{}_weights.h5'.format(model_name))

print("Model saved!")

# Generating Text

string_mapped = X[99]

print(string_mapped)

full_string = [n_to_char[value] for value in string_mapped]
# generating characters
for i in range(10):
    x = np.reshape(string_mapped, (1, len(string_mapped), 1))

    x = x / float(len(characters))

    pred_index = np.argmax(model.predict(x, verbose=0))

    seq = [n_to_char[value] for value in string_mapped]

    full_string.append(n_to_char[pred_index])

    string_mapped.append(pred_index)
    string_mapped = string_mapped[1:len(string_mapped)]

# Merging results
txt = ''
for char in full_string:
    txt = txt+char

print(txt)
