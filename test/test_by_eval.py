
import unittest
from command_utils import load_arguments
import os
import bleualign
import io
from bleualign.align import Aligner
from test.utils import Utils

class TestByEval(unittest.TestCase, Utils):
	def setUp(self):
		pass

	def test_originalFileName(self):
		self.main_test('fileNameOptions', remove_file = 'removeFile')
	def test_fileObject(self):
		self.main_test('fileObjectOptions',
			close_file_object = 'closeAllFiles',
			remove_file = 'removeFile')
	def test_stringIo(self):
		self.main_test('stringIoOptions')
	def test_string(self):
		self.main_test('stringOptions')
	def test_differentTypeOptions(self):
		self.main_test('differentTypeOptions',
			remove_file = 'removeTargetFile')

	def main_test(self, option_function,
			close_file_object = None, remove_file = None):
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
				output_file = self.output_file_path(srctotarget_file, targettosrc_file)
				output_path = os.path.join(result_dir , output_file)
				options = getattr(self, option_function)(test_argument,
					srctotarget_file, targettosrc_file, output_path)
				a = Aligner(options)
				a.mainloop()
				output_src, output_target = a.results()
				if close_file_object != None:
					getattr(self, close_file_object)([output_src, output_target])
					getattr(self, close_file_object)([options['targetfile']])
					getattr(self, close_file_object)(options['targettosrc'])
					if option_function == 'fileObjectOptions':
						getattr(self, close_file_object)([options['srcfile']])
						getattr(self, close_file_object)(options['srctotarget'])
				refer_path = os.path.join(refer_dir , output_file)
				compare_files.append((output_path + '-s', refer_path + '-s', output_src))
				compare_files.append((output_path + '-t', refer_path + '-t', output_target))
		# compare result with data in refer
		for result_path, refer_path, output_object in compare_files:
			self.cmp_files(result_path, refer_path, output_object)
			if remove_file != None:
				getattr(self, remove_file)(result_path)
	def fileNameOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = load_arguments(['', eval_type, '--srctotarget', '-'])
		options['srctotarget'] = srctotarget_file
		options['targettosrc'] = targettosrc_file
		options['output-src'] = output_file + '-s'
		options['output-target'] = output_file + '-t'
		options['verbosity'] = 0
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
				fileArray.append(io.open(fileName))
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
			f = io.open(options[attr])
			options[attr] = io.StringIO(f.read())
			f.close()
		for attr in 'srctotarget', 'targettosrc':
			ioArray = []
			for fileName in options[attr]:
				f = io.open(fileName)
				ioArray.append(io.StringIO(f.read()))
				f.close()
			options[attr] = ioArray
		return options
	def stringOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, srctotarget_file, targettosrc_file, output_file)
		options.pop('output-src')
		options.pop('output-target')
		for attr in 'srcfile', 'targetfile':
			f = io.open(options[attr])
			options[attr] = list(f)
			f.close()
		for attr in 'srctotarget', 'targettosrc':
			strArray = []
			for fileName in options[attr]:
				f = io.open(fileName)
				strArray.append(list(f))
				f.close()
			options[attr] = strArray
		return options
	def differentTypeOptions(self, eval_type,
				srctotarget_file, targettosrc_file, output_file):
		options = self.fileNameOptions(
			eval_type, srctotarget_file, targettosrc_file, output_file)
		# file object
		for attr in 'targetfile', :
			options[attr] = io.open(options[attr])
		# stringIO
		for attr in 'srctotarget', :
			ioArray = []
			for fileName in options[attr]:
				f = io.open(fileName)
				ioArray.append(io.StringIO(f.read()))
				f.close()
			options[attr] = ioArray
		# string array
		for attr in 'targettosrc', :
			strArray = []
			for fileName in options[attr]:
				f = io.open(fileName)
				strArray.append(list(f))
				f.close()
			options[attr] = strArray
		# stringIO
		options.pop('output-src')
		# filename: output-target
		return options
	def closeAllFiles(self, file_list):
		for file in file_list:
			file.flush()
			os.fsync(file.fileno())
			file.close()
	def removeFile(self, path):
		os.remove(path)
	def removeTargetFile(self, path):
		if path.endswith('-t'):
			self.removeFile(path)

if __name__ == '__main__':
	unittest.main()
