
import os
import itertools
import io

class Utils():
	def output_file_path(self, srctotarget_file, targettosrc_file):
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
	def cmp_files(self, result, refer, output_object):
		refer_file = io.open(refer)
		refer_data = refer_file.read()
		refer_file.close()
		try:
			result_data = output_object.getvalue()
		except:
			result_file = io.open(result)
			result_data = result_file.read()
			result_file.close()
		self.assertEqual(result_data, refer_data, result)
