
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
						fr_file, de_file, result_path)
	def runAndGetResult(self, eval_type,
				srctotarget_file, targettosrc_file,
				result_path):
		options = load_arguments(['', eval_type])
		options['srctotarget'] = [srctotarget_file]
		options['targettosrc'] = [targettosrc_file]
		s2t_set, s2t_trans = os.path.basename(srctotarget_file).split('.')[:2]
		t2s_set, t2s_trans = os.path.basename(targettosrc_file).split('.')[:2]
		if s2t_set != t2s_set:
			raise RuntimeError
		print(srctotarget_file,targettosrc_file)
		print(s2t_set, s2t_trans, t2s_trans)
		output_filename = '.'.join([s2t_set, s2t_trans, t2s_trans])
		options['output'] = os.path.join(result_path , output_filename)
# 		sys.stdout = open('hi', 'w')
		a = Aligner(options)
		a.mainloop()

if __name__ == '__main__':
	unittest.main()
