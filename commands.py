import sublime, sublime_plugin

from .ts import util, persist
import subprocess

textsync = persist.textsync()

class TextsyncStartSync(sublime_plugin.WindowCommand):
	def is_enabled(self):
		return not persist.textsync().enabled()

	def run(self):
		persist.textsync().enabled(True)

class TextsyncStopSync(sublime_plugin.WindowCommand):
	def is_enabled(self):
		return persist.textsync().enabled()

	def run(self):
		persist.textsync().enabled(False)


def runProcess(exe):    
    p = subprocess.Popen(exe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while(True):
      retcode = p.poll() #returns None while subprocess is running
      line = p.stdout.readline()
      yield line
      if(retcode is not None):
        break

import os

class TextsyncStartServer(sublime_plugin.WindowCommand):
	def is_enabled(self):
		return not persist.server_state()

	def run(self):
		persist.start_server()
		print("Start", persist.server_state())
		persist.server_state(True)

class TextsyncStopServer(sublime_plugin.WindowCommand):
	def is_enabled(self):
		return persist.server_state()

	def run(self):
		persist.storage.server.stop()


class TextsyncChooseSyncModeSlow(sublime_plugin.WindowCommand):
	def run(self, value=None):
		persist.speed_setting("Slow")

		persist.settings.set("minSyncInterval", 800)
		persist.settings.set("syncInterval", 1000)
		persist.settings.set("maxSyncInterval", 2000)
		persist.settings.save()
		

	def is_checked(self):
		return persist.speed_setting() == "Slow"

class TextsyncChooseSyncModeNormal(sublime_plugin.WindowCommand):
	def run(self, value=None):
		persist.speed_setting("Normal")

		persist.settings.set("minSyncInterval", 400)
		persist.settings.set("syncInterval", 700)
		persist.settings.set("maxSyncInterval", 1500)
		persist.settings.save()
		

	def is_checked(self):
		return persist.speed_setting() == "Normal"

class TextsyncChooseSyncModeFast(sublime_plugin.WindowCommand):
	def run(self, value=None):
		persist.speed_setting("Fast")

		persist.settings.set("minSyncInterval", 200)
		persist.settings.set("syncInterval", 400)
		persist.settings.set("maxSyncInterval", 800)
		persist.settings.save()
		

	def is_checked(self): 
		return persist.speed_setting() == "Fast"


class TextsyncChooseCursorStyle(sublime_plugin.WindowCommand):
	def style_name(self):
		return None

	def run(self, value=None):
		persist.settings.set("ghost_cursor", self.style_name())
		persist.settings.save()
		
	def is_checked(self):
		return persist.settings.get("ghost_cursor") == self.style_name()

class TextsyncChooseCursorStyleFill(TextsyncChooseCursorStyle):
	def style_name(self):
		return "fill"

class TextsyncChooseCursorStyleOutline(TextsyncChooseCursorStyle):
	def style_name(self):
		return "outline"

class TextsyncChooseCursorStyleSolidUnderline(TextsyncChooseCursorStyle):
	def style_name(self):
		return "solid underline"

class TextsyncChooseCursorStyleSquigglyUnderline(TextsyncChooseCursorStyle):
	def style_name(self):
		return "squiggly underline"

class TextsyncChooseCursorStyleStippledUnderline(TextsyncChooseCursorStyle):
	def style_name(self):
		return "stippled underline"


class TextsyncToggleDebug(sublime_plugin.WindowCommand):
	def run(self, value=None):
		print("Setting debug mode:",not persist.settings.get("debug"))
		persist.settings.set("debug", not persist.settings.get("debug"))
		persist.settings.save()