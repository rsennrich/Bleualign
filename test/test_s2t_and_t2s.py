
import unittest
import os
from bleualign.align import Aligner

class TestS2tAndT2s(unittest.TestCase):
	def setUp(self):
		pass
	def atest_1989googlefr(self):
		current_path = os.path.dirname(os.path.abspath(__file__))
		eval1989de = os.path.join(current_path, '..', 'eval', 'eval1989.de')
		eval1989fr = os.path.join(current_path, '..', 'eval', 'eval1989.fr')
		googlefr = os.path.join(current_path, '..', 'eval', 'eval1989.google.fr')
		self._sameResultForEval(eval1989de, eval1989fr, [googlefr], [])
	def test_same1989googlefr(self):
		current_path = os.path.dirname(os.path.abspath(__file__))
		eval1989de = os.path.join(current_path, '..', 'eval', 'eval1989.de')
		eval1989fr = os.path.join(current_path, '..', 'eval', 'eval1989.fr')
		googlefr = os.path.join(current_path, '..', 'eval', 'eval1989.google.fr')
		with open(eval1989de) as f:
			de_small = f.readlines()[602:625]
		with open(eval1989fr) as f:
			fr_small = f.readlines()[608:634]
		with open(googlefr) as f:
			go_small = f.readlines()[602:625]
		self._sameResultForEval(de_small, fr_small, [go_small], [])
	def _sameResultForEval(self,de,fr,s2t,t2s):
		options = {
			'srcfile':de,
			'targetfile':fr,
			'srctotarget':s2t,
			'targettosrc':t2s,
			'verbosity':0,
			}
		a = Aligner(options)
		a.mainloop()
		output_src, output_target = a.results()
		s2t_src = output_src.getvalue().splitlines()
		s2t_trg = output_target.getvalue().splitlines()
		options = {
			'srcfile':fr,
			'targetfile':de,
			'srctotarget':t2s,
			'targettosrc':s2t,
			'verbosity':0,
			}
		a = Aligner(options)
		a.mainloop()
		output_src, output_target = a.results()
		t2s_src = output_src.getvalue().splitlines()
		t2s_trg = output_target.getvalue().splitlines()
		self.assertEqual(s2t_src, t2s_trg)
		self.assertEqual(s2t_trg, t2s_src)

if __name__ == '__main__':
	unittest.main()
