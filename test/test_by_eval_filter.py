
import unittest
from command_utils import load_arguments
import os
import bleualign
import io
from bleualign.align import Aligner
from test.utils import Utils

class TestByEvalFilter(unittest.TestCase, Utils):
	def setUp(self):
		pass

	def test_originalFileName(self):
		self.main_test('fileNameOptions')
	def test_fileObject(self):
		self.main_test('fileObjectOptions')
	def test_stringIo(self):
		self.main_test('stringIoOptions')

	def main_test(self, option_function):
		test_dir = os.path.dirname(os.path.abspath(__file__))
		eval_dir = os.path.join(test_dir, '..', 'eval')
		result_dir = os.path.join(test_dir, 'result')
		refer_dir = os.path.join(test_dir, 'refer')
		bleualign.log = lambda a, b:None
		compare_files = []
		for test_set, test_argument in [('eval1957', '-d'), ('eval1989', '-e')]:
			fr_text = []
			de_text = []
			for filename in os.listdir(eval_dir):
				if filename.startswith(test_set):
					attr = filename.split('.')
					if len(attr) == 3:
						filepath = os.path.join(eval_dir, filename)
						if attr[1] != 'clean':
							if attr[2] == 'fr':
								fr_text.append(filepath)
							elif attr[2] == 'de':
								de_text.append(filepath)
			fr_text.sort()
			de_text.sort()
			test_files = []
			test_files.append((fr_text[0:1], de_text[-3:-2], 'articles'))
			test_files.append((fr_text, [], 'sentences'))
			test_files.append((fr_text, de_text, 'sentences'))
			for fr_file, de_file, filter_type in test_files:
				srctotarget_file = fr_file
				targettosrc_file = de_file
				output_file = self.output_file_path(srctotarget_file, targettosrc_file)
				output_path = os.path.join(result_dir , output_file)
				options = getattr(self, option_function)(test_argument, filter_type,
					srctotarget_file, targettosrc_file, output_path)
				a = Aligner(options)
				a.mainloop()
				output_src, output_target = a.results()
				output_src_bad, output_target_bad = a.results_bad()
				if option_function == 'fileObjectOptions':
					output_src.close()
					output_target.close()
					output_src_bad.close()
					output_target_bad.close()
				refer_path = os.path.join(refer_dir , output_file)
				compare_files.append((output_path + '-good-s', refer_path + '-good-s', output_src))
				compare_files.append((output_path + '-good-t', refer_path + '-good-t', output_target))
				compare_files.append((output_path + '-bad-s', refer_path + '-bad-s', output_src_bad))
				compare_files.append((output_path + '-bad-t', refer_path + '-bad-t', output_target_bad))
		for result_path, refer_path, output_object in compare_files:
			self.cmp_files(result_path, refer_path, output_object)
			if option_function.startswith('file'):
				os.remove(result_path)
	def fileNameOptions(self, eval_type, filter_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type,\
			'--filter', filter_type,\
			'--srctotarget', '-'])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		options['output-src'] = output_file + '-good-s'
		options['output-target'] = output_file + '-good-t'
		options['output-src-bad'] = output_file + '-bad-s'
		options['output-target-bad'] = output_file + '-bad-t'
		options['verbosity'] = 0
		if filter_type == 'articles':
			options['filterthreshold'] = 50
		return options
	def fileObjectOptions(self, eval_type, filter_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, filter_type, srctotarget_file, targettosrc_file, output_file)
		for attr in 'output-src', 'output-target', 'output-src-bad', 'output-target-bad':
			options[attr] = io.open(options[attr], 'w')
		return options
	def stringIoOptions(self, eval_type, filter_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, filter_type, srctotarget_file, targettosrc_file, output_file)
		for attr in 'output-src', 'output-target', 'output-src-bad', 'output-target-bad':
			options[attr] = io.StringIO()
		return options

if __name__ == '__main__':
	unittest.main()
