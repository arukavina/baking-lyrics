from docopt import docopt
import pickle
import numpy as np
import pandas as pd
import math

from sklearn.model_selection import train_test_split
from nltk.corpus import gutenberg
from nltk.corpus.reader.plaintext import PlaintextCorpusReader

from languagemodeling.ngram import NGram, AddOneNGram
#InterpolatedNGram


models = {
    'ngram': NGram,
    'addone': AddOneNGram
 #   'inter': InterpolatedNGram,
}


if __name__ == '__main__':

    # load the data

    from nltk.corpus import PlaintextCorpusReader
    corpus_root = 'C://Users//fmonczor//Documents//GitHub//PLN-UBA2018_//languagemodeling//Texto'
    corpus = PlaintextCorpusReader(corpus_root, '.*')
    sents = corpus.sents('Facundo.txt')

    n = 4

    # Dividing into test and train
    train,test = train_test_split(sents,test_size=0.1, random_state=1)

    model_class = AddOneNGram
    model = model_class(n, train)

    log_prob = model.log_prob(test)
    n = sum(len(test) + 1 for sent in test)  # count '</s>' event
    e = - log_prob / n
    p = math.pow(2.0, e)

    print('Log probability: {}'.format(log_prob))
    print('Cross entropy: {}'.format(e))
    print('Perplexity: {}'.format(p))



