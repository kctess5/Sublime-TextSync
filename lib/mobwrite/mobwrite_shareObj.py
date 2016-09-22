import urllib

from .diff_match_patch import diff_match_patch

DIFF_EQUAL = 0

class ShareObj(object):
	"""docstring for ShareObj"""
	def __init__(self, id):
		self.dmp = diff_match_patch()
		self.dmp.Diff_Timeout = 0.5

		self.file = id
		self.editStack = []
		self.shadowText = ''
		self.clientVersion = 0
		self.serverVersion = 0
		self.deltaOk = False
		self.mergeChanges = True

	def getClientText(self):
		print("Defined By Subclass (you shouldn't ever see this)")
		return ''

	def setClientText(self):
		print("Defined By Subclass (you shouldn't ever see this)")

	def patchClientText(self, patches):
		oldClientText = self.getClientText()
		result = self.dmp.patch_apply(patches, oldClientText)
		if not oldClientText == result[0]:
			self.setClientText(result[0])

	def onSentDiff(self, diffs):
		pass
	def nullify(self):
		self.mobwrite.unshare(self)
		return 'N:' + self.mobwrite.idPrefix + self.file + '\n'
	def syncText(self):
		clientText = self.getClientText()

		if not self.mobwrite:
			self.persist.log.info('Bailing out on syncText: no mobwrite client')
			return ''
		if not clientText:
			self.persist.log.info('Bailing out on syncText: no text')
			return ''

		if self.deltaOk:
			diffs = self.dmp.diff_main(self.shadowText, clientText, True)
			if len(diffs) > 2:
				self.dmp.diff_cleanupSemantic(diffs)
				self.dmp.diff_cleanupEfficiency(diffs)
			changed = not len(diffs) == 1 or not diffs[0][0] == DIFF_EQUAL

			if changed:
				self.mobwrite.clientChange_ = True
				self.shadowText = clientText
			if changed or not self.editStack:
				action = ('d:' if self.mergeChanges else 'D:') + str(self.clientVersion)
				action += ':' + self.dmp.diff_toDelta(diffs)
				self.editStack.append([self.clientVersion, action])
				self.clientVersion += 1
				self.onSentDiff(diffs)
		else:
			self.shadowText = clientText
			self.clientVersion += 1
			action = 'r:' + str(self.clientVersion) + ':' 
			action += urllib.parse.quote_plus(clientText).replace('%20', ' ')
			self.editStack.append([self.clientVersion, action])
			self.deltaOk = True
		data = 'F:' + str(self.serverVersion) + ":"
		data += self.mobwrite.idPrefix + self.file + '\n'

		for edit in self.editStack:
			data += edit[1] + '\n'

		data += self.constructMessage()

		return data
	def unshare(self):
		self.mobwrite.unshare(self)

	def constructMessage(self):
		# Should be defined in super class. Could be used for cursor position info, etc.
		return ''
	def handleMessage(self, *args):
		pass # defined by super









