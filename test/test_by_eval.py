
import unittest
from bleualign import Aligner, load_arguments
import os
import sys
import itertools

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
		test_path = os.path.dirname(os.path.abspath(__file__))
		eval_path = os.path.join(test_path, '..', 'eval')
		result_path = os.path.join(test_path, 'result')
		for test_set, test_argument in [('eval1957', '-d'), ('eval1989', '-e')]:
			fr_text = []
			de_text = []
			for filename in os.listdir(eval_path):
				if filename.startswith(test_set):
					attr = filename.split('.')
					if len(attr) == 3:
						filepath = os.path.join(eval_path, filename)
						if attr[2] == 'fr':
							fr_text.append(filepath)
						elif attr[2] == 'de':
							de_text.append(filepath)
			fr_text.sort()
			de_text.sort()
# 			print(fr_text, de_text)
			for fr_file in fr_text:
				for de_file in de_text:
					self.runAndGetResult(test_argument,
						[fr_file], [de_file], result_path)
	def runAndGetResult(self, eval_type,
				srctotarget_file, targettosrc_file,
				result_path):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		source_set = set()
		source_trans = []
		for filename in itertools.chain.from_iterable(
				(srctotarget_file, ['..'], targettosrc_file)):
			filename_set, filename_trans = os.path.basename(filename).split('.')[:2]
			source_set.add(filename_set)
			source_trans.append(filename_trans)
		source_set.discard('')
		if len(source_set) > 1:
			raise RuntimeError
		output_filename = '.'.join(
			itertools.chain.from_iterable(([source_set.pop()],source_trans)))
		options['output'] = os.path.join(result_path , output_filename)
# 		sys.stdout = open('hi', 'w')
		a = Aligner(options)
		a.mainloop()

if __name__ == '__main__':
	unittest.main()
