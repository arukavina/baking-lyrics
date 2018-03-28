from collections import defaultdict
import random


class NGramGenerator(object):

    def __init__(self, model):
        """
        model -- n-gram model.
        """
        self._n = model._n

        # compute the probabilities
        probs = defaultdict(dict)
        for ngram, count in model._count.items():
            if len(ngram) == self._n:
                probs[ngram[:-1]][ngram[-1]] = count / model._count[ngram[:-1]]
        self._probs = probs

        # sort in descending order for efficient sampling
        my_sorted = lambda xs: sorted(xs, key=lambda x: (-x[1], x[0]))
        self._sorted_probs = sorted_probs = {}
        for prev_tokens, prob_dict in probs.items():
            sorted_probs[prev_tokens] = my_sorted(prob_dict.items())

    def generate_sent(self):
        """Randomly generate a sentence."""
        n = self._n

        sent = []
        prev_token = ['<s>'] * (n - 1)
        token = self.generate_token(tuple(prev_token))
        token_list = prev_token
        i = 1

        while token != '</s>':
            token_list.append(token)
            prev_token = token_list[i:]
            sent.append(token)
            token = self.generate_token(tuple(prev_token))
            i += 1

        return sent


    def generate_token(self, prev_tokens=None):
        """Randomly generate a token, given prev_tokens.

        prev_tokens -- the previous n-1 tokens (optional only if n = 1).
        """
        n = self._n
        if not prev_tokens:
            prev_tokens = ()
        assert len(prev_tokens) == n - 1

        r = random.random()
        probs = self._sorted_probs[prev_tokens]
        token, prob = probs[0]
        i = 0
        acum = prob

        while r > acum:
            i += 1
            token, prob = probs[i]
            acum += prob

        return token



