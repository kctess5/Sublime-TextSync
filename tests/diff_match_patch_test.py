import unittest, sys, os

sys.path.append(os.path.join('..', 'lib', 'mobwrite'))
sys.path.append(os.path.join('lib', 'mobwrite'))

import diff_match_patch

class TestDiffMatchPatch(unittest.TestCase):
	def setUp(self):
		self.dmp = diff_match_patch.diff_match_patch()

	def test_normal_match_insert(self):
		shadowText = "abcabcabbc"
		actualText = "abcabcabbc"
		newText = "abcabcxabbc"

		# abc|a|b|c|a|b|b|c -> abc|a|b|c|xa|b|b|c
		# 3,4,5,6,7,8,9 -> 3,4,5,6,8,9,10
		# 
		# [0, 1, 2, 3, 4, 5, 6]

		offsets = [3,4,5,6,7,8,9]

		diffs = self.dmp.diff_main(shadowText, newText)

		patches = self.dmp.patch_make(shadowText, diffs)
		serverResult = self.dmp.patch_apply(patches, actualText, offsets)

		# print(serverResult[2])

		self.assertEqual(serverResult[0], "abcabcxabbc")
		self.assertEqual(serverResult[2], [3,4,5,6,8,9,10])

	def test_fuzzy_match_insert(self):
		shadowText = "abcabc"
		actualText = "abcabbc"
		newText = "abcxabc"

		# |a|b|c|a|b|b|c -> |a|b|c|xa|b|b|c
		# 0,1,2,3,4,5,6 -> 0,1,2,3,5,6,7

		offsets = [0,1,2,3,4,5,6]

		diffs = self.dmp.diff_main(shadowText, newText)

		patches = self.dmp.patch_make(shadowText, diffs)
		serverResult = self.dmp.patch_apply(patches, actualText, offsets)

		# print(serverResult[2])

		self.assertEqual(serverResult[0], "abcxabbc")
		self.assertEqual(serverResult[2], [0,1,2,3,5,6,7])

	def test_fuzzy_match_delete(self):
		shadowText = "abcabc"
		actualText = "abcabbc"
		newText = "ababc"

		# |a|b|c|a|b|b|c -> |a|b||a|b|b|c
		# 0,1,2,3,4,5,6 -> 0,1,2,2,3,4,5

		offsets = [0,1,2,3,4,5,6]

		diffs = self.dmp.diff_main(shadowText, newText)

		patches = self.dmp.patch_make(shadowText, diffs)
		serverResult = self.dmp.patch_apply(patches, actualText, offsets)

		self.assertEqual(serverResult[0], "ababbc")
		self.assertEqual(serverResult[2], [0,1,2,2,3,4,5])


if __name__ == '__main__':
	unittest.main()