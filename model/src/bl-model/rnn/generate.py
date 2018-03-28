#!/usr/bin/env python
"""
RNN Keras Model Factory.
"""

# Generic

# Libs
import numpy as np

# Keras
from keras.utils import np_utils
from keras.models import model_from_yaml


text = (open("../../../data/martin-fierro.txt").read())
text = text.lower().strip()

characters = sorted(list(set(text)))
n_to_char = {n: char for n, char in enumerate(characters)}
char_to_n = {char: n for n, char in enumerate(characters)}

X = []
Y = []
length = len(text)

print(text[1])
print(length)

seq_length = 100

for i in range(0, length - seq_length, 1):
    sequence = text[i:i + seq_length]
    label = text[i + seq_length]
    X.append([char_to_n[char] for char in sequence])
    Y.append(char_to_n[label])
    #print(label, '->', Y)


X_modified = np.reshape(X, (len(X), seq_length, 1))
X_modified = X_modified / float(len(characters))
Y_modified = np_utils.to_categorical(Y)

big = False

if big:
    model_name = 'text_generator_700_0.2_700_0.2_700_0.2_100_big'

else:
    model_name = 'text_generator_400_0.2_400_0.2_100'

# Load YAML and create model
yaml_file = open("../../../models/{}_model.yaml".format(model_name), 'r')

loaded_model_yaml = yaml_file.read()
yaml_file.close()
loaded_model = model_from_yaml(loaded_model_yaml)

# Load weights into new model
loaded_model.load_weights('../../../models/{}_weights.h5'.format(model_name))
print("Loaded model from disk")

# Generating Text

string_mapped = X[231]

print(string_mapped)

full_string = [n_to_char[value] for value in string_mapped]

txt = ''
for char in full_string:
    txt = txt+char

print('Base: ')
print('----------')
print(txt)
print('----------')


full_string = []

# Generating N characters

for i in range(100):
    x = np.reshape(string_mapped, (1, len(string_mapped), 1))

    x = x / float(len(characters))

    pred_index = np.argmax(loaded_model.predict(x, verbose=0))
    # print(pred_index, '->', n_to_char[pred_index])

    seq = [n_to_char[value] for value in string_mapped]

    full_string.append(n_to_char[pred_index])

    string_mapped.append(pred_index)
    string_mapped = string_mapped[1:len(string_mapped)]

# Merging results
txt = ''
for char in full_string:
    txt = txt+char

print('Generated: ')
print('----------')
print(txt)
print('----------')
