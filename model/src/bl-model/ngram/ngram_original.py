# https://docs.python.org/3/library/collections.html
from collections import defaultdict
import math


class LanguageModel(object):

    def sent_prob(self, sent):
        """Probability of a sentence. Warning: subject to underflow problems.

        sent -- the sentence as a list of tokens.
        """
        return 0.0

    def sent_log_prob(self, sent):
        """Log-probability of a sentence.

        sent -- the sentence as a list of tokens.
        """
        return -math.inf

    def log_prob(self, sents):
        result = 0.0
        for i, sent in enumerate(sents):
            lp = self.sent_log_prob(sent)
            if lp == -math.inf:
                return lp
            result += lp
        return result

    def cross_entropy(self, sents):
        log_prob = self.log_prob(sents)
        n = sum(len(sent) + 1 for sent in sents)  # count '</s>' events
        e = - log_prob / n
        return e

    def perplexity(self, sents):
        return math.pow(2.0, self.cross_entropy(sents))


class NGram(LanguageModel):

    def __init__(self, n, sents):
        """
        n -- order of the model.
        sents -- list of sentences, each one being a list of tokens.
        """
        assert n > 0
        self._n = n

        count = defaultdict(int)

        for sent in sents:
            # add start and end markers
            sent = ['<s>'] * (n - 1) + sent + ['</s>']
            for i in range(len(sent) - n + 1):
                ngram = tuple(sent[i: i + n])
                count[ngram] += 1
                count[ngram[:-1]] += 1

        self._count = dict(count)

    def count(self, tokens):
        """Count for an n-gram or (n-1)-gram.

        tokens -- the n-gram or (n-1)-gram tuple.
        """
        return self._count.get(tokens, 0)

    def cond_prob(self, token, prev_tokens=None):
        n = self._n
        if not prev_tokens:
            prev_tokens = ()
        assert len(prev_tokens) == n - 1
        assert isinstance(prev_tokens, tuple), prev_tokens

        tokens = prev_tokens + (token,)
        if tokens in self._count:
            return float(self._count[tokens]) / self._count[prev_tokens]
        else:
            return 0.0

    def sent_prob(self, sent):
        """Probability of a sentence. Warning: subject to underflow problems.

        sent -- the sentence as a list of tokens.
        """
        sent = sent + ['</s>']
        prob = 1.0
        prev_tokens = ('<s>',) * (self._n - 1)
        for token in sent:
            cond_prob = self.cond_prob(token, prev_tokens)
            if cond_prob == 0.0:
                return 0.0
            prob *= cond_prob
            prev_tokens = (prev_tokens + (token,))[1:]

        return prob

    def sent_log_prob(self, sent):
        """Log-probability of a sentence.

        sent -- the sentence as a list of tokens.
        """
        sent = sent + ['</s>']
        log_prob = 0.0
        prev_tokens = ('<s>',) * (self._n - 1)
        for token in sent:
            cond_prob = self.cond_prob(token, prev_tokens)
            if cond_prob == 0.0:
                return -math.inf
            log_prob += math.log(cond_prob, 2)
            prev_tokens = (prev_tokens + (token,))[1:]

        return log_prob
