# -*- coding: utf-8 -*-
import os
from distutils.core import setup
from setuptools import find_packages

def read_file(filename):
	return open(os.path.join(os.path.dirname(__file__), filename)).read()

setup(
	name = 'bleualign',
	version = '0.1.0',
	description = 'An MT-based sentence alignment tool',
	long_description = read_file('README.md'),
	author = 'Rico Sennrich ',
	author_email = 'sennrich@cl.uzh.ch',
	url = 'https://github.com/rsennrich/Bleualign',
	download_url = 'https://github.com/rsennrich/Bleualign',
	keywords = [
		'Sentence Alignment',
		'Natural Language Processing',
		'Statistical Machine Translation',
		'BLEU',
		],
	classifiers = [
		# which Development Status?
		'Development Status :: 3 - Alpha',
		'Development Status :: 4 - Beta',
		'Development Status :: 5 - Production/Stable',
		'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2.6',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.2',
		'Programming Language :: Python :: 3.3',
		'Programming Language :: Python :: 3.4',
		'Topic :: Scientific/Engineering',
		'Topic :: Scientific/Engineering :: Information Analysis',
		'Topic :: Text Processing',
		'Topic :: Text Processing :: Linguistic',
	],
	packages = find_packages(),
	package_data = {'': ['eval/ev*', 'test/refer/*', 'test/result/.keep']},
)
