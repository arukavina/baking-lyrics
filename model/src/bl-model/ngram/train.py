"""Train an n-gram model.

Usage:
  train.py [-m <model>] -n <n> -o <file>
  train.py -h | --help

Options:
  -n <n>        Order of the model.
  -m <model>    Model to use [default: ngram]:
                  ngram: Unsmoothed n-grams.
                  addone: N-grams with add-one smoothing.
                  inter: N-grams with interpolation smoothing.
  -o <file>     Output model file.
  -h --help     Show this screen.
"""
from docopt import docopt
import pickle
import numpy as np
import pandas as pd
import math

from sklearn.model_selection import train_test_split
from nltk.corpus import gutenberg
from nltk.corpus.reader.plaintext import PlaintextCorpusReader

from languagemodeling.ngram import NGram, AddOneNGram
from languagemodeling import ngram_generator
#InterpolatedNGram


models = {
    'ngram': NGram,
    'addone': AddOneNGram
 #   'inter': InterpolatedNGram,
}


if __name__ == '__main__':
    opts = docopt(__doc__)

    # load the data
    sents = gutenberg.sents(['austen-emma.txt', 'austen-sense.txt'])
    train,test = train_test_split(sents,test_size=0.1, random_state=1)

    # text_file = open('chestertontest.txt',"w")
    # for sent in test:
    #      text_file.write("%s\n" % sent)
    # text_file.close()

    n = int(opts['-n'])

    # model = NGram(n, train)
    model_class = models[opts['-m']]
    model = model_class(n, train)

    log_prob = model.log_prob(test)
    n = sum(len(test) + 1 for sent in test)  # count '</s>' event
    e = - log_prob / n
    p = math.pow(2.0, e)

    print('Log probability: {}'.format(log_prob))
    print('Cross entropy: {}'.format(e))
    print('Perplexity: {}'.format(p))


    # save it
    filename = opts['-o']
    f = open(filename, 'wb')
    pickle.dump(model, f)
    f.close()
