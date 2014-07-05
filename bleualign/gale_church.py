# -*- coding: utf-8 -*-
from __future__ import division
import math

# Based on Gale & Church 1993, 
# "A Program for Aligning Sentences in Bilingual Corpora"

infinity = float("inf")

def erfcc(x):
    """Complementary error function."""
    z = abs(x)
    t = 1 / (1 + 0.5 * z)
    r = t * math.exp(-z * z -
                     1.26551223 + t *
                     (1.00002368 + t *
                      (.37409196 + t *
                       (.09678418 + t *
                        (-.18628806 + t *
                         (.27886807 + t *
                          (-1.13520398 + t *
                           (1.48851587 + t *
                            (-.82215223 + t * .17087277)))))))))
    if (x >= 0.):
        return r
    else:
        return 2. - r


def norm_cdf(x):
    """Return the area under the normal distribution from M{-∞..x}."""
    return 1 - 0.5 * erfcc(x / math.sqrt(2))


class LanguageIndependent(object):
    # These are the language-independent probabilities and parameters
    # given in Gale & Church

    # for the computation, l_1 is always the language with less characters
    PRIORS = {
        (1, 0): 0.0099,
        (0, 1): 0.0099,
        (1, 1): 0.89,
        (2, 1): 0.089,
        (1, 2): 0.089,
        (2, 2): 0.011,
    }

    AVERAGE_CHARACTERS = 1
    VARIANCE_CHARACTERS = 6.8


def trace(backlinks, source, target):
    links = set()
    pos = (len(source) - 1, len(target) - 1)

    #while pos != (-1, -1):
    while pos[0] != -1 and pos[1] != -1:
        #print(pos)
        #print(backlinks)
        #print(backlinks[pos])
        s, t = backlinks[pos]
        for i in range(s):
            for j in range(t):
                links.add((pos[0] - i, pos[1] - j))
        pos = (pos[0] - s, pos[1] - t)

    return links


def align_probability(i, j, source_sentences, target_sentences, alignment, params):
    """Returns the probability of the two sentences C{source_sentences[i]}, C{target_sentences[j]}
    being aligned with a specific C{alignment}.

    @param i: The offset of the source sentence.
    @param j: The offset of the target sentence.
    @param source_sentences: The list of source sentence lengths.
    @param target_sentences: The list of target sentence lengths.
    @param alignment: The alignment type, a tuple of two integers.
    @param params: The sentence alignment parameters.

    @returns: The probability of a specific alignment between the two sentences, given the parameters.
    """
    l_s = sum(source_sentences[i - offset] for offset in range(alignment[0]))
    l_t = sum(target_sentences[j - offset] for offset in range(alignment[1]))
    try:
        # actually, the paper says l_s * params.VARIANCE_CHARACTERS, this is based on the C
        # reference implementation. With l_s in the denominator, insertions are impossible.
        m = (l_s + l_t / params.AVERAGE_CHARACTERS) / 2
        delta = (l_t - l_s * params.AVERAGE_CHARACTERS) / math.sqrt(m * params.VARIANCE_CHARACTERS)
    except ZeroDivisionError:
        delta = infinity

    return 2 * (1 - norm_cdf(abs(delta))) * params.PRIORS[alignment]


def align_blocks(source_sentences, target_sentences, params = LanguageIndependent):
    """Creates the sentence alignment of two blocks of texts (usually paragraphs).

    @param source_sentences: The list of source sentence lengths.
    @param target_sentences: The list of target sentence lengths.
    @param params: the sentence alignment parameters.

    @return: The sentence alignments, a list of index pairs.
    """
    alignment_types = list(params.PRIORS.keys())

    # there are always three rows in the history (with the last of them being filled)
    # and the rows are always |target_text| + 2, so that we never have to do
    # boundary checks
    D = [(len(target_sentences) + 2) * [0] for x in range(2)]

    # for the first sentence, only substitution, insertion or deletion are
    # allowed, and they are all equally likely ( == 1)

    D.append([0, 1])
    try:
      D[-2][1] = 1
      D[-2][2] = 1
    except:
      pass

    backlinks = {}

    for i in range(len(source_sentences)):
        for j in range(len(target_sentences)):
            m = []
            for a in alignment_types:
                k = D[-(1 + a[0])][j + 2 - a[1]]
                if k > 0:
                    p = k * \
                      align_probability(i, j, source_sentences, target_sentences, a, params)
                    m.append((p, a))

            if len(m) > 0:
                v = max(m)
                backlinks[(i, j)] = v[1]
                D[-1].append(v[0])
            else:
                backlinks[(i, j)] = (1, 1)
                D[-1].append(0)

        D.pop(0)
        D.append([0, 0])

    return trace(backlinks, source_sentences, target_sentences)


def align_texts(source_blocks, target_blocks, params = LanguageIndependent):
    """Creates the sentence alignment of two texts.

    Texts can consist of several blocks. Block boundaries cannot be crossed by sentence 
    alignment links. 

    Each block consists of a list that contains the lengths (in characters) of the sentences
    in this block.
    
    @param source_blocks: The list of blocks in the source text.
    @param target_blocks: The list of blocks in the target text.
    @param params: the sentence alignment parameters.

    @returns: A list of sentence alignment lists
    """
    if len(source_blocks) != len(target_blocks):
        raise ValueError("Source and target texts do not have the same number of blocks.")
    
    return [align_blocks(source_block, target_block, params) 
            for source_block, target_block in zip(source_blocks, target_blocks)]


def split_at(it, split_value):
    """Splits an iterator C{it} at values of C{split_value}. 

    Each instance of C{split_value} is swallowed. The iterator produces
    subiterators which need to be consumed fully before the next subiterator
    can be used.
    """
    def _chunk_iterator(first):
        v = first
        while v != split_value:
            yield v
            v = it.next()
    
    while True:
        yield _chunk_iterator(it.next())
        

def parse_token_stream(stream, soft_delimiter, hard_delimiter):
    """Parses a stream of tokens and splits it into sentences (using C{soft_delimiter} tokens) 
    and blocks (using C{hard_delimiter} tokens) for use with the L{align_texts} function.
    """
    return [
        [sum(len(token) for token in sentence_it) 
         for sentence_it in split_at(block_it, soft_delimiter)]
        for block_it in split_at(stream, hard_delimiter)]


if __name__ == "__main__":
    import sys
    from contextlib import nested
    
    with nested(open(sys.argv[1], "r"), open(sys.argv[2], "r")) as (s, t):
        source = parse_token_stream((l.strip() for l in s), ".EOS", ".EOP")
        target = parse_token_stream((l.strip() for l in t), ".EOS", ".EOP")
        print(align_texts(source, target))
