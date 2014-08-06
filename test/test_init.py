
import unittest
import os
from bleualign.align import Aligner

class TestByEval(unittest.TestCase):
	def setUp(self):
		current_path = os.path.dirname(os.path.abspath(__file__))
		self.srcfile = os.path.join(current_path, '..', 'eval', 'eval1989.de')
		self.targetfile = os.path.join(current_path, '..', 'eval', 'eval1989.fr')

	def test_no_src_or_target(self):
		self.assertRaises(ValueError, Aligner, {})
		self.assertRaises(ValueError, Aligner, {'srcfile':self.srcfile})
		self.assertRaises(ValueError, Aligner, {'targetfile':self.targetfile})
	def test_no_translation(self):
		self.assertRaises(ValueError, Aligner,
			{'srcfile':self.srcfile, 'targetfile':self.targetfile})
		a=Aligner(
			{'srcfile':self.srcfile, 'targetfile':self.targetfile, 'galechurch':True})
		a.close_file_streams()
		a=Aligner(
			{'srcfile':self.srcfile, 'targetfile':self.targetfile,
			'srctotarget':[self.targetfile]})
		a.close_file_streams()
		a=Aligner(
			{'srcfile':self.srcfile, 'targetfile':self.targetfile,
			'targettosrc':[self.srcfile]})
		a.close_file_streams()

if __name__ == '__main__':
	unittest.main()
