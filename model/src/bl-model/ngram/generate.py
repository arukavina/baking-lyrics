"""Generate natural language sentences using a language model.

Usage:
  generate.py -i <file> -n <n>
  generate.py -h | --help

Options:
  -i <file>     Language model file.
  -n <n>        Number of sentences to generate.
  -h --help     Show this screen.
"""
from docopt import docopt
import pickle

from languagemodeling.ngram_generator import NGramGenerator


if __name__ == '__main__':
    # opts = docopt(__doc__)
    #
    # # load the model
    # filename = opts['-i']
    # f = open(filename, 'rb')
    # model = pickle.load(f)
    # f.close()

    # build generator
    generator = NGramGenerator(model)

    # generate sentences
    n = int(opts['-n'])
    for i in range(n):
        sent = generator.generate_sent()
        print(' '.join(sent))
