
import unittest
from bleualign import Aligner, load_arguments, log
import os
import itertools
import sys
import bleualign

class TestByEval(unittest.TestCase):
	def setUp(self):
		self.options = {}
		self.options['srcfile'] = None
		self.options['targetfile'] = None
		self.options['output'] = None
		self.options['factored'] = False
		self.options['filter'] = None
		self.options['filterthreshold'] = 90
		self.options['filterlang'] = None
		self.options['srctotarget'] = []
		self.options['targettosrc'] = []
		self.options['eval'] = None
		self.options['galechurch'] = None
		self.options['verbosity'] = 1
		self.options['printempty'] = False

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
			test_files = []
			test_files.append((fr_text[0:1], de_text[-3:-2]))
			test_files.append((fr_text, []))
			test_files.append((fr_text[1::3], de_text[-2:-1]))
			test_files.append((fr_text[2:3], de_text[3:4]))
			test_files.append((fr_text[0:1], []))
			test_files.append((fr_text[2:], de_text[:3]))
			test_files.append((fr_text, de_text))
# 			test_files.append(([], [])) add in another test after
# 			test_files.append(([], de_text))
# 			test_files.append(([], de_text[-1:]))
			for fr_file, de_file in test_files:
				srctotarget_file = fr_file
				targettosrc_file = de_file
				output_file = self.output_file_path(result_path, srctotarget_file, targettosrc_file)
				options=self.fileOptions(test_argument,
					srctotarget_file, targettosrc_file, output_file)
# 				sys.stdout = open('hi', 'w')
				print(srctotarget_file, targettosrc_file, output_file)
				bleualign.log=lambda a,b:None
				a = Aligner(options)
				a.mainloop()
	def fileOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		options['output'] = output_file
		return options
	def output_file_path(self, result_path, srctotarget_file, targettosrc_file):
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
			itertools.chain.from_iterable(([source_set.pop()], source_trans)))
		return os.path.join(result_path , output_filename)

if __name__ == '__main__':
	unittest.main()
