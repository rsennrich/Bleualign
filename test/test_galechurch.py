
import unittest
from command_utils import load_arguments
import os
import bleualign
from bleualign.align import Aligner
from test.utils import Utils

class TestGaleChurch(unittest.TestCase, Utils):
	def setUp(self):
		pass
	def test_gale_church(self):
		test_dir = os.path.dirname(os.path.abspath(__file__))
		result_dir = os.path.join(test_dir, 'result')
		refer_dir = os.path.join(test_dir, 'refer')
		bleualign.log = lambda a, b:None
		compare_files = []
		for test_set, test_argument in [('eval1957', '-d'), ('eval1989', '-e')]:
			options = load_arguments(['', test_argument, '--srctotarget', '-'])
			options ['galechurch'] = False
			output_file = test_set + '-galechurch'
			output_path = os.path.join(result_dir , output_file)
			options['output'] = output_path
			a = Aligner(options)
			a.mainloop()
			output_src, output_target = a.results()
			refer_path = os.path.join(refer_dir , output_file)
			compare_files.append((output_path + '-s', refer_path + '-s', output_src))
			compare_files.append((output_path + '-t', refer_path + '-t', output_target))
		# compare result with data in refer
		for result_path, refer_path, output_object in compare_files:
			self.cmp_files(result_path, refer_path, output_object)

if __name__ == '__main__':
	unittest.main()
