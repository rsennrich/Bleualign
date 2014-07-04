
import unittest
from bleualign import Aligner, load_arguments
import os
import itertools
import bleualign
import io

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

	def test_originalFileName(self):
		self.main_test('fileNameOptions')
	def test_fileObject(self):
		self.main_test('fileObjectOptions')
	def test_stringIo(self):
		self.main_test('stringIoOptions')
	def test_string(self):
		self.main_test('stringOptions')

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
				output_src, output_target = a.mainloop()
# 				time.sleep(5)
				# compare result with data in refer
				refer_path = os.path.join(refer_dir , output_file)
				compare_files.append((output_path + '-s', refer_path + '-s', output_src))
				compare_files.append((output_path + '-t', refer_path + '-t', output_target))
# 				self.cmp_files(output_path + '-s', refer_path + '-s')
# 				self.cmp_files(output_path + '-t', refer_path + '-t')
		for result_path, refer_path, output_object in compare_files:
			self.cmp_files(result_path, refer_path, output_object)
	def cmp_files(self, result, refer, output_object):
		refer_file = io.open(refer)
		refer_data = refer_file.read()
		refer_file.close()
		try:
			result_file = io.open(result)
			result_data = result_file.read()
			result_file.close()
		except:
			result_data = output_object.getvalue()
		self.assertEqual(result_data, refer_data, result)
	def fileNameOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		options['output-src'] = output_file + '-s'
		options['output-target'] = output_file + '-t'
		return options
	def fileObjectOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, srctotarget_file, targettosrc_file, output_file)
		for attr in 'srcfile', 'targetfile':
			options[attr] = io.open(options[attr])
		for attr in 'srctotarget', 'targettosrc':
			fileArray = []
			for fileName in options[attr]:
				fileArray.append(fileName)
			options[attr] = fileArray
		for attr in 'output-src', 'output-target':
			options[attr] = io.open(options[attr], 'w')
		return options
	def stringIoOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, srctotarget_file, targettosrc_file, output_file)
		options.pop('output-src')
		options.pop('output-target')
		for attr in 'srcfile', 'targetfile':
			options[attr] = io.StringIO(io.open(options[attr]).read())
		for attr in 'srctotarget', 'targettosrc':
			ioArray = []
			for fileName in options[attr]:
				ioArray.append(io.StringIO(io.open(fileName).read()))
			options[attr] = ioArray
		return options
	def stringOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, srctotarget_file, targettosrc_file, output_file)
		options.pop('output-src')
		options.pop('output-target')
		for attr in 'srcfile', 'targetfile':
			options[attr] = list(io.open(options[attr]))
		for attr in 'srctotarget', 'targettosrc':
			strArray = []
			for fileName in options[attr]:
				strArray.append(list(io.open(fileName)))
			options[attr] = strArray
		return options
	def fileInStringOutOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		return options, options['output-src'], options['output-target']
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
