
import unittest
from bleualign import Aligner, load_arguments
import os
import itertools
import bleualign
import filecmp
import time

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

	def test_original_file_option(self):
		self.main_test('fileOptions')

	def main_test(self, option_function):
		test_dir = os.path.dirname(os.path.abspath(__file__))
		eval_dir = os.path.join(test_dir, '..', 'eval')
		result_dir = os.path.join(test_dir, 'result')
		refer_dir = os.path.join(test_dir, 'refer')
		bleualign.log = lambda a, b:None
		compare_files=[]
		for test_set, test_argument in [('eval1957', '-d'), ('eval1989', '-e')]:
			fr_text = []
			de_text = []
			for filename in os.listdir(eval_dir):
				if filename.startswith(test_set):
					attr = filename.split('.')
					if len(attr) == 3:
						filepath = os.path.join(eval_dir, filename)
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
				output_file = self.output_file_path(result_dir, srctotarget_file, targettosrc_file)
				output_path = os.path.join(result_dir , output_file)
				options = getattr(self, option_function)(test_argument,
					srctotarget_file, targettosrc_file, output_path)
				a = Aligner(options)
				a.mainloop()
# 				time.sleep(5)
				# compare result with data in refer
				refer_path = os.path.join(refer_dir , output_file)
				compare_files.append((output_path + '-s', refer_path + '-s'))
				compare_files.append((output_path + '-t', refer_path + '-t'))
# 				self.cmp_files(output_path + '-s', refer_path + '-s')
# 				self.cmp_files(output_path + '-t', refer_path + '-t')
		for result_path, refer_path in compare_files:
			self.cmp_files(result_path, refer_path)
	def cmp_files(self,result,refer):
		result_file=open(result)
		refer_file=open(refer)
		result_data=list(result_file)
		refer_data=list(refer_file)
		result_file.close()
		refer_file.close()
		self.assertEqual(result_data,refer_data,result)
	def fileOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		options['output'] = output_file
		return options
	def output_file_path(self, result_dir, srctotarget_file, targettosrc_file):
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
		return output_filename

if __name__ == '__main__':
	unittest.main()
