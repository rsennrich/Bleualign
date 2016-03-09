#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: University of Zurich
# Author: Rico Sennrich

# script to allow batch-alignment of multiple files. No multiprocessing.
# syntax: python batch_align directory source_suffix target_suffix translation_suffix
#
# example: given the directory batch-test with the files 0.de, 0.fr and 0.trans, 1.de, 1.fr and 1.trans and so on,
# (0.trans being the translation of 0.de into the target language),
# then this command will align all files: python batch_align.py batch-test/ de fr trans
#
# output files will have ending source_suffix.aligned and target_suffix.aligned


import sys
import os
from bleualign.align import Aligner

if len(sys.argv) < 5:
    sys.stderr.write('Usage: python batch_align directory source_suffix target_suffix translation_suffix\n')
    exit()

directory = sys.argv[1]
source_suffix = sys.argv[2]
target_suffix = sys.argv[3]
translation_suffix = sys.argv[4]

options = {}
options['factored'] = False
options['filter'] = None
options['filterthreshold'] = 90
options['filterlang'] = None
options['targettosrc'] = []
options['eval'] = None
options['galechurch'] = None
options['verbosity'] = 1
options['printempty'] = False
options['output'] = None

jobs = []

for source_document in [d for d in os.listdir(directory) if d.endswith('.' + source_suffix)]:

    source_document = os.path.join(directory, source_document)
    target_document = source_document[:-len(source_suffix)] + target_suffix
    translation_document = source_document[:-len(source_suffix)] + translation_suffix

    # Sanity checks
    for f in source_document, target_document, translation_document:
        if not os.path.isfile(f):
            sys.stderr.write('ERROR: File {0} expected, but not found\n'.format(f))
            exit()

    jobs.append((source_document, target_document, translation_document))

for (source_document,target_document,translation_document) in jobs:

    options['srcfile'] = source_document
    options['targetfile'] = target_document
    options['srctotarget'] = [translation_document]
    options['output-src'] = source_document + '.aligned'
    options['output-target'] = target_document + '.aligned'

    a = Aligner(options)
    a.mainloop()
