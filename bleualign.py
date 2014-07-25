#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright © 2010 University of Zürich
# Author: Rico Sennrich <sennrich@cl.uzh.ch>
# For licensing information, see LICENSE

import sys
from command_utils import load_arguments
from bleualign.align import Aligner

if __name__ == '__main__':
    options = load_arguments(sys.argv)

    a = Aligner(options)
    a.mainloop()
