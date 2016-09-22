import os, sys, json, time, copy
import socket
import sublime
from glob import glob

from . import highlight


# from ..lib.diff_match_patch import diff_match_patch as dmp
from ..lib.mobwrite.mobwrite_client import MobwriteClient
from ..lib.mobwrite.mobwrite_shareObj import ShareObj

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/requests"))

import requests

DESCRIPTOR_NAME = "textsync.settings"

# a file gained focus
VIEW_FOCUS_COEF = 0.75 # decrease

# a file lost focus
VIEW_UNFOCUS_COEF = 0.5 # increase

def parseDirectory(text):
	if not text:
		return ""
	lastSlash = text.rfind('/')
	if lastSlash < 0:
		return ""

	return text[0:lastSlash + 1]

def allViews(generator=True):
	if generator:
		return ( view for window in sublime.windows() for view in window.views() )
	else:
		return [ view for window in sublime.windows() for view in window.views() ]

def toHexString(value):
	"""  Returns a clean hex (no hash) string for a given input  """
	
	return str(hex(value))[2:]

def stringToColor(string):
	"""  Returns a random color (e.g. 'AB55FF') given a string.
		 The same input string will return the same color.
	"""
	
	unique_string = hash(string)

	r = (unique_string & 0xFF0000) >> 16;
	g = (unique_string & 0x00FF00) >> 8;
	b = unique_string & 0x0000FF;

	return toHexString(r) + toHexString(g) + toHexString(b)

def walk_up(bottom):
	""" 
	mimic os.walk, but walk 'up'
	instead of down the directory tree
	"""
 
	bottom = os.path.realpath(bottom)
 
	#get files in current dir
	try:
		names = os.listdir(bottom)
	except Exception as e:
		print(e)
		return
 
 
	dirs, nondirs = [], []
	for name in names:
		if os.path.isdir(os.path.join(bottom, name)):
			dirs.append(name)
		else:
			nondirs.append(name)
 
	yield bottom, dirs, nondirs
 
	new_path = os.path.realpath(os.path.join(bottom, '..'))
	
	# see if we are at the top
	if new_path == bottom:
		return
 
	for x in walk_up(new_path):
		yield x

# @lru_cache(maxsize=None) # needs proper cache-busting
def getRepoForView(view):
	"""  Scans the directory structure for repo descriptor.
		 If a descriptor is found, a repo object is constructed and returned.
	"""
	directory = parseDirectory(view.file_name())

	for root, dirs, files in walk_up(directory):
		repo = Repo(root)

		if repo.isInitialized():
			return repo

	return False

def matchGlob(base, relative_glob):
	"""  Returns a set of matching filenames  """
	
	full_glob = os.path.join(base, relative_glob)
	return set( glob(full_glob) )

def clear_caches():
	# getRepoForView.clear_cache()
	pass

class Repo:
	"""  One repo per textsync repository. Manages settings interface and util functionality.  """
	def __init__(self, path):

		self.path = path
		self.initialized = False
		self.descriptor = {}

		self.load()

	def getMatches(self):
		if not self.isInitialized():
			return []

		includes = set()

		for relative_glob in self.descriptor['include']:
			includes |= matchGlob(self.path, relative_glob)

		excludes = set()

		for relative_glob in self.descriptor['exclude']:
			excludes |= matchGlob(self.path, relative_glob)

		return includes.difference( excludes )

	def owns(self, view):
		"""  Compares a view to the file globs to see if it is part of this repo.
			 Returns True if so, False otherwise  
		"""
		
		matches = self.getMatches()

		return view.file_name() in matches

	def isInitialized(self):
		return self.initialized

	def load(self):
		"""  Attempts to load a repo descriptor from a given path.
			 If a descriptor is found, it is loaded into self.descriptor,
			 and self.initialized is set to True  
		"""
		
		filePath = self.path + '/' + DESCRIPTOR_NAME

		if os.path.isfile(filePath):
			with open(filePath, 'r') as f:
				self.descriptor = json.loads(f.read() or "{}")
				self.initialized = True

			# print('sharing', self.id())

	def relPath(self, view):
		"""  Returns the relative repo path for a given view.
			 Used to remove extra file path from the absolute path.  
		"""

		filename = view.file_name()
		return filename[ len( self.path ) + 1: ]

	def gateway(self):
		"""  Returns the network gateway for this repo. This should be the
			 internet address of a MobWrite server  
		"""
		
		if not self.isInitialized():
			return False

		return self.descriptor['gateway']

	def id(self):
		return self.get('id')

	def get(self, attr):
		return self.descriptor[attr]

class Transport:
	"""  Network interface wrapper. Manages requests. One transport per mobwrite server.  """

	no_gateway_msg = "Err! No gateway! Check textsync.settings file for \"gateway\" attribute."

	def __init__(self, gateway, log):
		log("Constructing transport")
		self.gateway = gateway
		self.log = log
		
	def transmit(self, query):
		# send message over the socket
		if not self.gateway:
			return self.log(no_gateway_msg)
			
		self.log(query)

		payload = {
			"query": query
		}

		return requests.post( self.gateway, data=payload )

class ShareViewComponent(ShareObj):
	"""  Manages file sync for one view.  """
	
	def __init__(self, view, repo, client):
		client.persist.log.debug("Constructing ShareViewComponent")

		self.view = view
		self.repo = repo
		self.persist = client.persist
		self.client  = client
		self.cursors = highlight.GhostCursorSet( self )
		self.was_modified = False
		
		super().__init__( self.serialize() )

		self.loadFileInfo() # check for previously defined file version info
		
	def getClientText(self):
		# persist.log.debug("TEXT", self.view.substr( sublime.Region(0, self.view.size())  ))
		return self.view.substr( sublime.Region(0, self.view.size())  ) or " " 

	def setClientText(self, text):
		self.persist.textsync().own(self.view)
		if text:
			self.view.run_command('set_text', {'text': text})
		self.persist.textsync().disown(self.view) 

	def storeFileInfo(self):
		self.persist.log.debug("Storing version settings:", self.clientVersion, self.serverVersion)
		self.persist.setOldSettings( self.serialize(), self )

	def loadFileInfo(self):
		oldSettings = self.persist.getOldSettings( self.serialize() )

		if oldSettings:
			self.persist.log.debug("Loading old version settings:", oldSettings['clientVersion'], oldSettings['serverVersion'])
			self.shadowText = oldSettings['shadowText']
			self.clientVersion = oldSettings['clientVersion']
			self.serverVersion = oldSettings['serverVersion']

	def serialize(self):
		return self.repo.relPath(self.view)

	def patchClientText(self, patches):
		"""  This method applies a list of patches, and corrects modified cursor locations.  """
		
		offsets = [] # offsets holds the positions of the various cursors
		ts = self.persist.textsync()
		view_lock = ts.view_lock(self.view)

		view_lock.acquire()
		# ts.own(self.view)

		try:
			print("doing change")
			selection = self.view.sel()

			self.was_modified = False
			
			for region in selection:
				offsets.append( region.begin() )
				offsets.append( region.end() )

			oldClientText = self.getClientText()
			
			selection.clear()

			result = self.dmp.patch_apply(patches, oldClientText, offsets)

			if self.was_modified:
				print("CONCURRENCY ERROR 1 - expect the unexpected.")

			self.setClientText(result[0])

			corrected_offsets = result[2]

			for i in range(0, len(offsets), 2):
				selection.add( sublime.Region(corrected_offsets[i], corrected_offsets[i + 1]) )

		finally:
			print("releasing lock")
			# ts.disown(self.view)
			view_lock.release()

		# end of atomic part

	def constructMessage(self):
		selection = self.view.sel()

		serialized = [ ( sel.begin(), sel.end() ) for sel in selection ]
		message = {
			"nickname": self.repo.get('username') or self.persist.settings.get('username', 'Anonymous User'),
			"selection": serialized
		}
		message = json.dumps( message, separators=(',',':') )

		return 'M:' + message + '\n' # instructs server to respond with all other available messages

	def handleMessage(self, message):
		self.cursors.handle_message( message )

	def terminate(self):
		self.cursors.terminate()

	def modified(self):
		self.was_modified = True

class TextSyncClient(MobwriteClient):
	"""  This acts as the adapter between textsync and MobWrite.  """
	
	def __init__(self, gateway, repo, persist):
		self.persist = persist
		self.persist.log.debug("Constructing textsyncClient")

		super().__init__(self.persist) # initialize mobwrite client

		self.timeoutInterval = self.persist.settings.get('timeoutInterval', 30000)
		self.minSyncInterval = self.persist.settings.get('minSyncInterval', 1000)
		self.maxSyncInterval = self.persist.settings.get('maxSyncInterval', 10000)
		self.syncInterval    = self.persist.settings.get('syncInterval',    2000)
		self.cookie          = self.persist.settings.get('cookie'   , None)
		self.IDSIZE          = self.persist.settings.get('IDSIZE'   , 8)
		self.enabled         = self.persist.settings.get('enabled', True)

		self.transport       = Transport( gateway, self.persist.log.debug )
		self.idPrefix        = self.constructIdPrefix(repo)
		self.logger          = self.persist.log
		self.syncUsername    = self.persist.settings.get('username', self.uniqueID())
		self.ShareComponents = {}

		self.events = {}

		self.events['focused']      = 0
		self.events['unfocused']    = 0

		if not gateway:
			self.logger.error('No network gateway specified!')

	def shareView(self, view, repo):
		newView = self.getShareComponent(view, repo)

		self.share(newView)

	def unshareView(self, view, repo):
		SC = self.getShareComponent(view, repo)
		ID = SC.serialize()

		if ID in self.shared:
			SC.storeFileInfo()
			self.shared[ID].unshare()

		# clean cache so a new component is created on next share
		if view.file_name() in self.ShareComponents:
			del self.ShareComponents[ view.file_name() ]

	def getShareComponent(self, view, repo):
		vid = view.file_name()

		if not vid in self.ShareComponents:
			self.ShareComponents[vid] = ShareViewComponent(view, repo, self)

		return self.ShareComponents[vid]

	def constructIdPrefix(self, repo):
		return repo.id()

	def destroy(self):
		shared = copy.copy(self.shared)

		for vid in shared:
			self.shared[vid].unshare()

		self.ShareComponents = {}

	def notifyModified(view):
		if view:
			vid = view.file_name()

			if vid in self.ShareComponents:
				self.ShareComponents[vid].modified()

	def notifyEvent(self, event, view):
		if event == 'was_modified':
			return self.notifyModified(view)

		if not event in self.events:
			self.events[ event ] = 1
		else:
			self.events[ event ] += 1

	def syncIntervalHook(self, range):

		if self.events['focused'] > 0:
			self.syncInterval -= r * VIEW_FOCUS_COEF
			self.events['focused'] = 0

		if self.events['unfocused'] > 0:
			self.syncInterval += r * VIEW_UNFOCUS_COEF
			self.events['unfocused'] = 0

class ClientManager:
	"""  Manages one Mobwrite client per mobwrite server. Each repo can
	     have a different server, so there may be one or many here.  
	"""
	
	def __init__(self, persist):
		persist.log.debug("Constructing clientManager")
		self.clients = {}
		self.persist = persist

	def shareView(self, view, repo):
		"""  Top level interface for sharing views.  """

		self.persist.log.debug("Tracking File:", view.file_name())
		self.getClient(repo).shareView(view, repo)

	def unshareView(self, view, repo):
		self.getClient(repo).unshareView(view, repo)

	def getClient(self, repo):
		serverAddr = repo.gateway()

		if not serverAddr:
			return False

		if not serverAddr in self.clients:
			self.clients[ serverAddr ] = TextSyncClient( serverAddr, repo, self.persist )

		return self.clients[ serverAddr ]

	def notifyEvent(self, view, event):
		"""  Notifies the correct client for the given view
			 that it recieved focus. Used for sync interval.  
		"""
		repo = getRepoForView(view)
		if repo:
			self.getClient(repo).notifyEvent(event, view)

	def reset(self):
		"""  Destroy all children. Refresh.  """
		
		for client in self.clients:
			self.clients[client].destroy()

		# All of these clients will be regenerated when they are required

		self.clients = {}



