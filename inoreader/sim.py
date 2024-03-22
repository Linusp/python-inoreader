import pickle
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from math import sqrt

PUNCTS_PAT = re.compile(
    r'(?:[#\$&@.,;:!?，。！？、：；  \u3300\'`"~_\+\-\*\/\\|\\^=<>\[\]\(\)\{\}（）“”‘’\s]|'
    r"[\u2000-\u206f]|"
    r"[\u3000-\u303f]|"
    r"[\uff30-\uff4f]|"
    r"[\uff00-\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65])+"
)


def make_terms(text, term, ngram_range=None, lower=True, ignore_punct=True, gram_as_tuple=False):
    if lower:
        text = text.lower()
    if term == "word":
        # term_seq = [word.strip() for word in jieba.cut(text) if word.strip()]
        term_seq = [word.strip() for word in text.split() if word.strip()]
    elif term == "char":
        term_seq = list(re.sub(r"\s", "", text))
    else:
        raise ValueError(f"unsupported term type: {term}")

    if ngram_range and not (len(ngram_range) == 2 and ngram_range[0] < ngram_range[1]):
        raise ValueError(f"wrong `ngram_range`: {ngram_range}")

    terms = []
    min_ngram, max_ngram = ngram_range or (1, 2)
    for idx in range(0, max(1, len(term_seq) - min_ngram + 1)):
        cur_grams = []
        for gram_level in range(min_ngram, max_ngram):
            if gram_as_tuple:
                gram = tuple(term_seq[idx : idx + gram_level])
            else:
                gram = "".join(term_seq[idx : idx + gram_level])
            if gram not in cur_grams:
                if ignore_punct and any(PUNCTS_PAT.match(item) for item in gram):
                    pass
                else:
                    cur_grams.append(gram)
        terms.extend(cur_grams)
    return terms


def lcs_sim(
    s1, s2, term="char", ngram_range=None, ngram_weights=None, lower=True, ignore_punct=True
):
    s1_terms = make_terms(s1, "char", None, lower, ignore_punct)
    s2_terms = make_terms(s2, "char", None, lower, ignore_punct)
    return SequenceMatcher(a=s1_terms, b=s2_terms).ratio()


def jaccard_sim(
    s1, s2, term="word", ngram_range=None, ngram_weights=None, lower=True, ignore_punct=True
):
    if not ngram_range or ngram_range[1] == ngram_range[0] + 1:
        first_term_set = set(make_terms(s1, term, ngram_range, lower, ignore_punct))
        second_term_set = set(make_terms(s2, term, ngram_range, lower, ignore_punct))
        if not first_term_set and not second_term_set:
            return 1.0
        return len(first_term_set & second_term_set) / len(first_term_set | second_term_set)
    else:
        weights = ngram_weights or list(range(*ngram_range))
        weights_sum = sum(weights)
        weights = [weight / weights_sum for weight in weights]
        scores = []
        for ngram_level in range(*ngram_range):
            score = jaccard_sim(
                s1,
                s2,
                term=term,
                ngram_range=(ngram_level, ngram_level + 1),
                lower=lower,
                ignore_punct=ignore_punct,
            )
            scores.append(score)

        return sum([score * weight for score, weight in zip(scores, weights)])


def cosine_sim(
    s1, s2, term="word", ngram_range=None, ngram_weights=None, lower=True, ignore_punct=True
):
    if not ngram_range or ngram_range[1] == ngram_range[0] + 1:
        first_term_freq = Counter(make_terms(s1, term, ngram_range, lower, ignore_punct))
        second_term_freq = Counter(make_terms(s2, term, ngram_range, lower, ignore_punct))

        first_norm = 0
        second_norm = 0
        inner_product = 0

        for term, freq in first_term_freq.items():
            first_norm += freq**2
            inner_product += freq * second_term_freq[term]

        for _, freq in second_term_freq.items():
            second_norm += freq**2

        if first_norm == 0 and second_norm == 0:
            return 1.0
        if first_norm == 0 or second_norm == 0:
            return 0.0

        return inner_product / sqrt(first_norm * second_norm)
    else:
        weights = ngram_weights or list(range(*ngram_range))
        weights_sum = sum(weights)
        weights = [weight / weights_sum for weight in weights]
        scores = []
        for ngram_level in range(*ngram_range):
            score = cosine_sim(
                s1,
                s2,
                term=term,
                ngram_range=(ngram_level, ngram_level + 1),
                lower=lower,
                ignore_punct=ignore_punct,
            )
            scores.append(score)

        return sum([score * weight for score, weight in zip(scores, weights)])


def sim_of(s1, s2, method="cosine", term="word", ngram_range=None, lower=True, ignore_punct=True):
    method_func = {
        "lcs": lcs_sim,
        "jaccard": jaccard_sim,
        "cosine": cosine_sim,
    }.get(method)
    if not method_func:
        raise ValueError("unsupported method: {}".format(method))

    return method_func(
        s1, s2, term=term, ngram_range=ngram_range, lower=lower, ignore_punct=ignore_punct
    )


class InvIndex(object):
    def __init__(self):
        """build inverted index with ngram method"""
        self._id2doc = {}
        self._index = defaultdict(set)

    def add_doc(self, doc):
        if doc.id in self._id2doc:
            return False

        self._id2doc[doc.id] = doc.title
        terms = set(make_terms(doc.title, "char", (3, 4)))
        for term in terms:
            self._index[term].add(doc.id)

        return True

    def retrieve(self, query, k=10):
        related = Counter()
        terms = set(make_terms(query, "char", (3, 4)))
        for term in terms:
            for qid in self._index.get(term, []):
                related[qid] += 1

        return [(idx, self._id2doc[idx], score) for idx, score in related.most_common(k)]

    def save(self, fname):
        pickle.dump((self._id2doc, self._index), open(fname, "wb"))

    def load(self, fname):
        self._id2doc, self._index = pickle.load(open(fname, "rb"))
