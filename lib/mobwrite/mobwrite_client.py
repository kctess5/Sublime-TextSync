"""  Ported to Python by Corey Walsh. 

	 Adapted from Google's MobWrite, written by Neil Fraser  

"""

import random, urllib, time, traceback, sublime

from threading import Thread

DIFF_EQUAL = 0

"""  How much the sync interval changes when:  """
# a remote change is recieved
REMOTE_CHANGE_COEF = 0.25 # decrease

# a local change is recieved
LOCAL_CHANGE_COEF = 0.5 # decrease

# nothing is recieved
DAMPING_COEF = 0.03 # increase

def clamp(n, minn, maxn):
	return max(min(maxn, n), minn)

class MobwriteClient(object):
	"""  Init function must be defined by the client adapter!  """

	def __init__(self, persist):
		# self.timeoutInterval = ???
		# self.minSyncInterval = ???
		# self.maxSyncInterval = ???
		# self.syncInterval    = ???
		# self.idPrefix        = ???
		# self.cookie          = ???
		# self.IDSIZE          = ???
		# self.transport       = ???
		# self.logger          = ???
		# self.syncUsername    = ???

		self.clientChange_   = False
		self.serverChange_   = False
		self.nullifyAll      = False
		self.shared          = {}
		self.syncThread      = None
		self.enabled         = True

		persist.registerClient(self)
		self.persist = persist

	def uniqueID(self):
		soup = "abcdefghijklmnopqrstuvwxyz"
		uId = [ random.choice(soup) for i in range(self.IDSIZE) ]

		soup += "0123456789-_:.";
		uId2 = [ random.choice(soup) for i in range(self.IDSIZE) ]

		uId = ''.join(uId) + ''.join(uId2)

		if '--' in uId:
			return self.uniqueID()

		return uId
	def syncRun1_(self):
		self.clientChange_ = False
		data = []
		data.append("u:" + self.syncUsername + '\n')

		empty = True

		for key in self.shared:
			share = self.shared[key]
			if self.nullifyAll:
				data.append(share.nullify())
			else:
				data.append(share.syncText())
			empty = False

		if empty:
			return

		if len(data) <= 1: # no sync data
			self.logger.info("All objects silent; null sync.")
			self.syncRun2_("\n\n")
			return

		data.append('\n');
		data = "".join(data)

		self.logger.debug("TO server:\n" + data)

		response = self.postToServer(data)

		self.syncRun2_(response)
	def syncRun2_(self, response):
		self.serverChange_ = False
		text = response.text
		self.logger.debug('From Server:\n' + text)

		if not text.endswith('\n\n'):
			text = ''
			self.logger.info('Truncated Data. Abort')

		lines = text.split('\n')
		f = None
		clientVersion = None

		for line in lines:
			if not line.strip(): # returns false if empty line
				break
			if not line[1] == ':':
				self.logger.info('Unparsable Line:' + line)

			name = line[0]
			value = line[2:]

			version = None
			if name in 'FfDdRr':
				div = value.index(':')
				if div < 1:
					self.logger.error('No Version Number: ' + line)
				version = int(value[:div])
				if not version and not version == 0:
					self.logger.error("Nan version number: " + line)
				value = value[div + 1:]

			if name in 'Ff':
				# self.logger.info(value[:len(self.idPrefix)] == self.idPrefix, 'test')
				if value[:len(self.idPrefix)] == self.idPrefix:
					value = value[len(self.idPrefix):]
				else:
					f = None
					self.logger.error("File does not have \"" + self.idPrefix + "\" prefix: " + value)
				if value in self.shared:
					f = self.shared[value]
					f.deltaOk = True
					clientVersion = version
					f.editStack = [ edit for edit in f.editStack if edit[0] > clientVersion ]
				else:
					# file is not currently shared
					f = None
					self.logger.error('Unknown File: ' + value)
			elif name in 'Rr':
				if f:
					f.shadowText = urllib.parse.unquote(value)
					f.clientVersion = clientVersion
					f.serverVersion = version
					f.editStack = []
					if name == 'R':
						f.setClientText(f.shadowText)
					self.serverChange_ = True
			elif name in 'Dd':
				if f:
					if not clientVersion == f.clientVersion:
						f.deltaOk = False
						self.logger.error('Client version number mismatch.\n Expected: ' + str(f.clientVersion) + ' Got: ' + str(clientVersion))
					elif version > f.serverVersion:
						f.deltaOk = False
						self.logger.error('Server version in future.\n Expected: ' + str(f.serverVersion) + ' Got: ' + str(version))
					elif version < f.serverVersion:
						self.logger.warn('Server version in past.\n Expected: ' + str(f.serverVersion) + ' Got: ' + str(version))
					else:
						diffs = None
						try:
							diffs = f.dmp.diff_fromDelta(f.shadowText, value)
							f.serverVersion += 1
						except Exception as e:
							traceback.print_exc()
							print(e)
							f.deltaOk = False
							self.syncInterval = 0
							self.logger.error('Delta mismatch.\n' + urllib.parse.quote(f.shadowText))
						self.logger.debug('diffs', diffs)
						if diffs and ( not len(diffs) == 1 or not diffs[0][0] == DIFF_EQUAL ):
							"""  This part only corrects cursor position if the little "d" method is used.
								 Eventually the root cause of this problem should be fixed, for now, it's commented.
							"""
							
							# if name == 'D' and False:
							# 	f.shadowText = f.dmp.diff_text2(diffs)
							# 	try:
							# 		print("3")
							# 		f.setClientText(f.shadowText)
							# 	except Exception:
							# 		self.logger.error("Error calling setClientText on '" + f.file + "'")
							# else:
							# print(name)
							patches = f.dmp.patch_make(f.shadowText, diffs)
							self.logger.debug(patches)
							serverResult = f.dmp.patch_apply(patches, f.shadowText)
							self.logger.debug(serverResult)
							f.shadowText = serverResult[0]
							f.patchClientText(patches)

							self.serverChange_ = True
			elif name in 'mM':
				if f:
					f.handleMessage( value )
	def computeSyncInterval_(self):
		r = self.maxSyncInterval - self.minSyncInterval

		if self.clientChange_:
			self.syncInterval -= r * LOCAL_CHANGE_COEF

		if self.serverChange_:
			self.syncInterval -= r * REMOTE_CHANGE_COEF

		if not self.clientChange_ and not self.serverChange_:
			self.syncInterval += r * DAMPING_COEF

		if self.syncIntervalHook:
			self.syncIntervalHook(r) # higher level hook to modify syncInterval based on app logic

		self.syncInterval = clamp(self.syncInterval, self.minSyncInterval, self.maxSyncInterval)
	def share(self, shareObjs):
		if not isinstance(shareObjs, list):
			shareObjs = [shareObjs]
		for shareObj in shareObjs:
			shareObj.mobwrite = self
			self.shared[shareObj.file] = shareObj
			self.logger.info("Sharing shareObj: \"" + shareObj.file + "\"")
		if self.syncThread == None or not self.syncThread.isAlive():
			self.syncThread = SyncThread(self)
			self.syncThread.enable(self.enabled)
			if self.enabled:
				self.logger.debug("Starting thread with enable state: True")
			else:
				self.logger.debug("Starting thread with enable state: False")
			self.syncThread.start()
	def unshare(self, shareObjs):
		if not isinstance(shareObjs, list):
			shareObjs = [shareObjs]
		for shareObj in shareObjs:
			if self.shared.pop(shareObj.file, None) == None:
				self.logger.info("Ignoring \"" + shareObj.file + "\". Not currently shared.")
			else:
				shareObj.terminate()
				shareObj.mobwrite = None
				self.logger.info("Unshared: \"" + shareObj.file + "\"")

		if self.syncThread and not self.shared:
			self.logger.debug("Killing zombie thread")
			self.syncThread.stop()
			self.syncThread = None
	def modify(self, shareObj):
		if shareObj.file_name() in self.shared:
			self.shared[shareObj.file_name()]
	def postToServer(self, query):
		return self.transport.transmit(query)

class SyncThread(Thread):
	def __init__(self, client):
		super().__init__()

		self.isStopped = False
		self.client = client
		self.enable_state = True

		self.client.persist.registerThread(self)

	def stop(self):
		self.isStopped = True

	def enable(self, state=None):
		if not state == None:
			self.enable_state = state
		return self.enable_state

	def run(self):
		while self.client and self.client.shared and not self.isStopped:
			if self.enable():
				self.client.syncRun1_()
				self.client.computeSyncInterval_()
				self.client.persist.debug("sleeping:", self.client.syncInterval)
				time.sleep(self.client.syncInterval / 1000)
			else:
				self.client.logger.debug("Mobwrite disabled.")
				time.sleep(1.0)


		self.client.logger.info('MobWrite Stopped!')
