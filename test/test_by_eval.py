
import unittest
from bleualign import Aligner, load_arguments
import os
import sys

class TestByEval(unittest.TestCase):
	def setUp(self):
		self.options = {}
		self.options['srcfile'] = None
		self.options['targetfile'] = None
		self.options['output'] = None
		self.options['factored'] = False
		self.options['filter'] = None
		options = {}
		options['filterthreshold'] = 90
		options['filterlang'] = None
		options['srctotarget'] = []
		options['targettosrc'] = []
		options['eval'] = None
		options['galechurch'] = None
		options['verbosity'] = 1
		options['printempty'] = False

	def test_google(self):
		test_path=os.path.dirname(os.path.abspath(__file__))
		self.runAndGetResult('-e',
			[os.path.join(test_path, '..', 'eval', 'eval1957.google.fr')],
			[])
	def runAndGetResult(self, eval_type,
			srctotarget, targettosrc):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget
		options['targettosrc'] = targettosrc
		sys.stdout=open('hi','w')
		a = Aligner(options)
		a.mainloop()

if __name__ == '__main__':
	unittest.main()
