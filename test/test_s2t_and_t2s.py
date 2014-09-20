
import unittest
import os
from bleualign.align import Aligner

class TestS2tAndT2s(unittest.TestCase):
	def setUp(self):
		pass
	def test_sameResultForEval(self):
		current_path = os.path.dirname(os.path.abspath(__file__))
		options = {
			'srcfile':os.path.join(current_path, '..', 'eval', 'eval1989.de'),
			'targetfile': os.path.join(current_path, '..', 'eval', 'eval1989.fr'),
			'srctotarget': [os.path.join(current_path, '..', 'eval', 'eval1989.google.fr')],
			'targettosrc': [],
			'output-src': None, 'output-target': None,
			}
		a = Aligner(options)
		a.mainloop()
		output_src, output_target = a.results()
		s2t_src = output_src.getvalue().splitlines()
		s2t_trg = output_target.getvalue().splitlines()
		options = {
			'srcfile':os.path.join(current_path, '..', 'eval', 'eval1989.fr'),
			'targetfile': os.path.join(current_path, '..', 'eval', 'eval1989.de'),
			'srctotarget': [],
			'targettosrc': [os.path.join(current_path, '..', 'eval', 'eval1989.google.fr')],
			'output-src': None, 'output-target': None,
			}
		a = Aligner(options)
		a.mainloop()
		output_src, output_target = a.results()
		t2s_src = output_src.getvalue().splitlines()
		t2s_trg = output_target.getvalue().splitlines()
		self.assertEqual(s2t_src, t2s_trg)
		self.assertEqual(s2t_trg, t2s_src)
	def test_sameResultForSmallEval(self):
		eval1989de=[
			'Bald einmal sind wir an der Reihe , uns mit dieser tückischen Stelle auseinanderzusetzen . ',
			'Ein Anstieg über brüchiges Gelände führt uns zum obersten , dunklen Turm , der aus rau hem Nummuliten-Sandstein besteht .', 
			'Voll Freude klettern wir die halbe Seillänge über die Kante hinauf zur Spitze des Hauserhorns .',
			]
		eval1989fr=[
			"Bientôt c' est à notre tour de nous battre avec ce passage vicieux ." ,
			"Nous remontons ensuite un terrain délité jusqu' au dernier gendarme , le plus sombre , formé de grès nummulitique ." ,
			"Tout joyeux , nous parcourons la dernière demi-longueur sur l' arête et atteignons la cime du Hauserhorn ." ,
			"Au sommet II n' est que dix heures , la journée est magnifique , nous pouvons donc nous accorder une longue pause au sommet .", 
			"A côté de la masse du Mittler Selbsanft , le Tödi trône au sud dans toute sa puissance , au-dessus des prairies et des rochers de la Bifertenalpli et de la Röti .", 
			]
		googlefr=[
			"Bientôt, nous nous tournons vers nous attaquer à cet endroit délicat.",
			"Une hausse de site fragile nous mène au sommet, la tour sombre, qui se compose de bas nummulites grès rugueux.",
			"Plein de joie, nous montons la moitié de la hauteur sur le bord jusqu'au sommet de la corne Hauser.",
			]
		options = {
			'srcfile':eval1989de,
			'targetfile': eval1989fr,
			'srctotarget': [googlefr],
			'targettosrc': [],
			'output-src': None, 'output-target': None,
			}
		a = Aligner(options)
		a.mainloop()
		output_src, output_target = a.results()
		s2t_src = output_src.getvalue().splitlines()
		s2t_trg = output_target.getvalue().splitlines()
		options = {
			'srcfile':eval1989fr,
			'targetfile': eval1989de,
			'srctotarget': [],
			'targettosrc': [googlefr],
			'output-src': None, 'output-target': None,
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
