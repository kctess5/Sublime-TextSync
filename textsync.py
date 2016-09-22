import sublime, sublime_plugin
import sys, os, re, copy

from .ts import util, persist
from threading import Lock

reloading = {
	'happening': False,
	'shown': False
}

# Override default uncaught exception handler
def ts_uncaught_except(type, value, tb):
	message = ''.join(traceback.format_exception(type, value, tb))

	if message.find('/textsync/') != -1 or message.find('\\textsync\\') != -1:
		persist.log.error("Unhandled Exception", message)

def reload_modules(load_order, prfix):
	global ExcepthookChain

	persist.log.info('Reloading Modules')
	"""  Force modules to reload - improves development workflow
		 https://www.sublimetext.com/forum/viewtopic.php?f=6&t=6777#p28977  
	"""

	st_version = 2
	if int(sublime.version()) > 3000:
		st_version = 3

	reload_mods = []
	for mod in sys.modules:
		if mod[:8] == prfix and sys.modules[mod] != None:
			reload_mods.append(mod)
			reloading['happening'] = True

	if st_version == 3:
		from imp import reload

	for mod in load_order:
		if mod in reload_mods:
			reload(sys.modules[mod])

	if sys.version_info < (3,):
		version_complain()

prefix = 'textsync'

def plugin_loaded():
	""" Plugin entry point """
	print()

	reload_modules([
		'textsync',
		'textsync.ts',
		'textsync.ts.highlight',
		'textsync.ts.util',
		'textsync.ts.persist',
		
		# 'textsync.lib',
		'textsync.lib.mobwrite.diff_match_patch',
		'textsync.lib.mobwrite.mobwrite_core',
		'textsync.lib.mobwrite.mobwrite_client',
		'textsync.lib.mobwrite.mobwrite_shareObj'
	], prefix)

	persist.settings.load(force=True) # This will cause all the threads to be restarted

	persist.printf("test",persist.settings.get("debug"))
	persist.printf('Loading Plugin. Debug mode:', 'on' if persist.debug_mode() else 'off -> turn it on if you have a problem.')
	if not persist.storage.plugin:
		persist.storage.plugin = textsync()

	persist.plugin_is_loaded = True
	
class textsync:
	""" The main ST3 plugin class. The majority of the application logic lives here """

	# We use this to match settings filenames.
	SETTINGS_RE = re.compile('^textsync(-.+?)?\.sublime-settings')

	def __init__(self):
		"""Initialize a new instance."""

		persist.log.info("Initializing textsync.")

		persist.storage.plugin = self

		# Keeps track of which views we are tracking
		self.new_watchlist = set()
		self.owned = set()
		self.tracked = {}
		self.view_locks = {}

		self.clientManager = util.ClientManager(persist)
		persist.settings.on_update_call(self.on_settings_updated)
		self.initOpen()

	def initOpen(self):
		"""  Initializes all open views.  """

		for view in util.allViews():
			# ignore unnamed files and files that don't exist in the file system
			if view.file_name() and os.path.exists( view.file_name() ): 
				self.init_view(view)

	def reset(self):
		"""  Reinitialize the plugin to reflect new settings.  """

		# preemptively killing threads prevents potential hanging references
		persist.destroy_all_threads()

		self.clientManager.reset()
		persist.settings.on_update_call(self.on_settings_updated)
		
		# persist.destroy_all_threads() # but this *should* work just as well
		persist.clear_caches()

		self.tracked = {}

	def on_settings_updated(self):
		"""Callback triggered when the settings are updated."""
		
		persist.debug("Settings Updated", persist.settings.settings)

		self.reset()
		self.initOpen()

	def init_view(self, view):
		repo = util.getRepoForView(view)

		if repo and repo.owns(view):
			self.track(view, repo)

	def destroy_view(self, view):
		self.untrack(view)

	def own(self, view):
		self.owned.add(view.file_name())

	def disown(self, view):
		self.owned.discard(view.file_name())

	def isOwned(self, view):
		return view.file_name() in self.owned

	def view_lock(self, view):
		""" Returns a mutex lock for a view """
		if view.file_name() not in self.view_locks:
			self.view_locks[ view.file_name() ] = Lock()

		return self.view_locks[ view.file_name() ]

	def track(self, view, repo):
		if view.file_name() in self.tracked:
			# Don't share an already active file!
			return

		self.tracked[ view.file_name() ] = view
		self.view_locks[ view.file_name() ] = Lock()

		self.clientManager.shareView(view, repo)

	def untrack(self, view):
		repo = util.getRepoForView(view)

		if repo and view.file_name() in self.tracked:
			persist.debug("Untracking File:", view.file_name())

			self.clientManager.unshareView(view, repo)
			del self.tracked[ view.file_name() ]

	def enabled(self, state=None):
		if not state == None:
			persist.settings.set('enabled', state)
			persist.settings.save()
		return persist.settings.get('enabled', True)

class textsyncEventListener(sublime_plugin.EventListener):
	""" This object watches for file events and handles them accordingly. """

	def __init__(self, *args, **kwargs):
		"""Initialize a new instance."""
		super().__init__(*args, **kwargs)

		self.textsync = persist.textsync()

		persist.log.info("Initializing EventListener")

	def check_for_plugin(f):
		"""  Decorator function. Executes input only if self.textsync is defined.  """
		
		def decorated(instance, view):
			if not instance.textsync:
				instance.textsync = persist.storage.plugin

				if not instance.textsync:
					return False
				
			f(instance, view)

		return decorated

	"""  Sublime Plugin Events  """

	@check_for_plugin
	def on_new_async(self, view):
		self.textsync.new_watchlist.add( view.id() )
		self.textsync.init_view(view)

	@check_for_plugin
	def on_load_async(self, view):
		self.textsync.init_view(view)
	
	@check_for_plugin
	def on_pre_close(self, view):
		self.textsync.destroy_view(view)
	
	@check_for_plugin
	def on_close(self, view):
		self.textsync.new_watchlist.discard( view.id() )
	
	@check_for_plugin
	def on_post_save_async(self, view):
		if view.id() in self.textsync.new_watchlist:
			self.textsync.init_view(view)
			self.textsync.new_watchlist.remove( view.id() )

	@check_for_plugin
	def on_activated_async(self, view):
		"""  Allows the mobwrite client to modify sync interval accordingly.  """
		self.textsync.clientManager.notifyEvent(view, 'focus')

	@check_for_plugin
	def on_deactivated_async(self, view):
		"""  Allows the mobwrite client to modify sync interval accordingly.  """
		self.textsync.clientManager.notifyEvent(view, 'unfocus')

	@check_for_plugin
	def on_modified(self, view):
		"""  Allows the plugin to detect edits at key times.  """

		was_user_initiated = not self.textsync.isOwned(view)

		persist.log.debug("User initiated modification:", was_user_initiated)

		# this function blocks the UI thread until it returns,
		# so we acquire the lock and promptly release it before
		# returning to ensure that no edits are happening concurrently
		# if the file is owned while there is a modification then
		# there is probably no need to
		
		persist.log.debug("If you see this message right before the UI freezes, then there is a deadlock error that must be addressed, please contact the maintainer of TextSync plugin.")

		if was_user_initiated:
			self.textsync.view_lock(view).acquire()
			self.textsync.view_lock(view).release()
	

		# as soon as we return, there will be a modification, so
		# notify just in case anyone out there cares

		# self.textsync.clientManager.notifyEvent(view, 'modified')

"""  Sublime Commands  """

class SetTextCommand(sublime_plugin.TextCommand):
	def run(self, edit, text=''):  
		if text: 
			self.view.replace(edit, sublime.Region(0, self.view.size()), text)
