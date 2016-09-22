# Heavily adapted from SublimeLinter3, original file header:
# 
# persist.py
# Part of SublimeLinter3, a code checking framework for Sublime Text 3
#
# Written by Ryan Hileman and Aparajita Fishman
#
# Project: https://github.com/SublimeLinter/SublimeLinter3
# License: MIT
#

"""This module provides persistent global storage for other modules."""

from collections import defaultdict
from copy import deepcopy
import json
import os
import re
import sublime
import sys
import subprocess

def merge_user_settings(settings):
    """Return the default linter settings merged with the user's settings."""

    default = settings.get('default', {})
    user = settings.get('user', {})

    if user:
        default.update(user)

    debug("merge settings:", default)

    return default

PLUGIN_NAME = 'textsync'

# Get the name of the plugin directory, which is the parent of this file's directory
PLUGIN_DIRECTORY = os.path.basename(os.path.dirname(os.path.dirname(__file__)))

class Settings:

    """ This class provides global access to and management of plugin settings.

        It persists throught the duration of the Sublime session. It is reinitalized
        whenever sublime first loads.
    """

    def __init__(self):
        print("Constructing settings")
        """Initialize a new instance."""
        self.settings = {}
        self.previous_settings = {}
        self.changeset = set()
        self.plugin_settings = None
        self.on_update_callback = None

    def load(self, force=False):
        """Load the plugin settings."""
        if force or not self.settings:
            self.observe()
            self.on_update()
            self.observe_prefs()

    def has_setting(self, setting):
        """Return whether the given setting exists."""
        return setting in self.settings

    def get(self, setting, default=None):
        """Return a plugin setting, defaulting to default if not found."""
        return self.settings.get(setting, default)

    def set(self, setting, value, changed=False):
        """
        Set a plugin setting to the given value.

        Clients of this module should always call this method to set a value
        instead of doing settings['foo'] = 'bar'.

        If the caller knows for certain that the value has changed,
        they should pass changed=True.

        """
        self.copy()
        self.settings[setting] = value

        if changed:
            self.changeset.add(setting)

    def pop(self, setting, default=None):
        """
        Remove a given setting and return default if it is not in self.settings.

        Clients of this module should always call this method to pop a value
        instead of doing settings.pop('foo').

        """
        self.copy()
        return self.settings.pop(setting, default)

    def copy(self):
        """Save a copy of the plugin settings."""
        self.previous_settings = deepcopy(self.settings)

    def observe_prefs(self, observer=None):
        """Observe changes to the ST prefs."""
        prefs = sublime.load_settings('Preferences.sublime-settings')
        prefs.clear_on_change('textsync-pref-settings')
        prefs.add_on_change('textsync-pref-settings', observer or self.on_prefs_update)

    def observe(self, observer=None):
        """Observer changes to the plugin settings."""

        self.plugin_settings = sublime.load_settings('textsync.sublime-settings')
        log.info("Observing settings", self.plugin_settings.get("debug"))
        self.plugin_settings.clear_on_change('textsync-persist-settings')
        self.plugin_settings.add_on_change('textsync-persist-settings', observer or self.on_update)

    def on_update_call(self, callback):
        """Set a callback to call when user settings are updated."""
        self.on_update_callback = callback

    def on_update(self):
        """
        Update state when the user settings change.

        The settings before the change are compared with the new settings.
        Depending on what changes, various parts of the plugin reload.

        """

        settings = merge_user_settings(self.plugin_settings)
        self.settings.clear()
        self.settings.update(settings)

        self.changeset.clear()

        if self.on_update_callback:
            self.on_update_callback()

    def save(self, view=None):
        """
        Regenerate and save the user settings.

        User settings are updated with the default settings and the defaults
        from every linter, and if the user settings are currently being edited,
        the view is updated.

        """

        print("persist.save called")

        # self.load()

        # Fill in default linter settings
        settings = self.settings
        print(settings)

        filename = '{}.sublime-settings'.format(PLUGIN_NAME)

        # user_prefs_path = os.path.join(sublime.packages_path(), 'User', filename)
        # settings_views = []

        # if view is None:
        #     # See if any open views are the user prefs
        #     for window in sublime.windows():
        #         for view in window.views():
        #             if view.file_name() == user_prefs_path:
        #                 settings_views.append(view)
        # else:
        #     settings_views = [view]

        # if settings_views:
        #     def replace(edit):
        #         if not view.is_dirty():
        #             j = json.dumps({'user': settings}, indent=4, sort_keys=True)
        #             j = j.replace(' \n', '\n')
        #             view.replace(edit, sublime.Region(0, view.size()), j)

            # for view in settings_views:
            #     edits[view.id()].append(replace)
            #     # view.run_command('sublimelinter_edit')
            #     print("PERSIST.PY - unexpected edge case not implemented. Notify maintainer if problem is encountered.")
            #     view.run_command('save')
        # else:
        user_settings = sublime.load_settings('textsync.sublime-settings')
        user_settings.set('user', settings)
        sublime.save_settings('textsync.sublime-settings')

    def on_prefs_update(self):
        """Perform maintenance when the ST prefs are updated."""
        print("lib.persist.on_prefs_update Called")

class Log:
    def debug(self, *args):
        # debug('debug:', *args)
        pass
    def info(self, *args):
        printf('info:', *args)
    def warn(self, *args):
        printf('warn:', *args)
    def warning(self, *args):
        printf('warn:', *args)
    def error(self, *args):
        printf('error:', *args)
    def critical(self, *args):
        printf('critical:', *args)

from threading import Thread

class Server(Thread):
    """ Wraps the instantiation of the central server """
    def __init__(self):
        super(Server, self).__init__()
        self.p = None

    def run(self):
        server_state(True)
        # os.chdir(os.path.dirname(__file__)+'/../server/flask')

        # self.p = subprocess.Popen('python server.py'.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
        # print(os.path.dirname(__file__))


        os.chdir(os.path.dirname(__file__)+'/../server/appengine')
        port = storage.settings.get("server_port", 9999)
        admin_port = storage.settings.get("server_admin_port", 8000)
        api_port = storage.settings.get("server_api_port", 64493)
        dev_appserver_cmd = storage.settings.get("dev_appserver")
        command = dev_appserver_cmd \
                +' --port=' + str(port) \
                +' --admin_port=' + str(admin_port) \
                +' --api_port=' + str(api_port) \
                +" --host=" + str(storage.settings.get("server_hostname")) \
                + ' app.yaml'

        print(command)

        self.p = subprocess.Popen(command.split(), stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT)
        
        while(True):
            retcode = self.p.poll() #returns None while subprocess is running
            line = self.p.stdout.readline()
            print("server:",line,)
            if(retcode is not None):
                break
        print("Server finished.")
        storage.server = None
        server_state(False)

    def stop(self):
        if self.p:
            print("Killing server...")
            self.p.terminate()
            storage.server = None
            print("Server killed")
        return

class volatile_storage:
    """  Initialized once per sublime instance.  """
    
    def __init__(self):
        print("textsync: Initializing Volatile Storage")

        self.highlights    = {}
        self.file_settings = {}

        self.log      = Log()
        self.settings = Settings()

        self.threads = set()
        self.clients = set()
        self.plugin  = False
        self.server  = None

        self.server_started = False
        self.speed_setting = "Normal"

if 'plugin_is_loaded' not in globals() or True:
    storage = volatile_storage()

    # Set to true when the plugin is loaded at startup
    plugin_is_loaded = False

"""  Public interfaces  """

settings = storage.settings
log      = storage.log

def start_server():
    if storage.server:
        print("Killing existing server.")
        storage.server.stop()
        storage.server.join()
        storage.server = None
        print("Finished killing existing server")
    print("Starting server...")
    storage.server = storage.server or Server()
    storage.server.start()

def speed_setting(state=None):
    if not state == None:
        storage.speed_setting = state
    return storage.speed_setting

def server_state(state=None):
    if not state == None:
        storage.server_started = state
    return storage.server_started

def textsync():
    return storage.plugin

def debug_mode():
    """Return whether the "debug" setting is True."""
    return settings.get('debug')

def debug(*args):
    """Print args to the console if the "debug" setting is True."""

    if settings.get('debug'):
        printf(*args)

def printf(*args):
    """Print args to the console, prefixed by the plugin name."""
    print(PLUGIN_NAME + ': ', end='')

    for arg in args:
        print(arg, end=' ')

    print()

def getOldSettings(fileId):
    """  Returns old file info in case this file was opened before in the same session  """

    if fileId in storage.file_settings:
        return storage.file_settings[fileId]
    else:
        return False

def setOldSettings(fileId, shareObj):
    if fileId:
        storage.file_settings[fileId] = {
            "shadowText": shareObj.shadowText,
            "clientVersion": shareObj.clientVersion,
            "serverVersion": shareObj.serverVersion
        }

def reset():
    destroyAllThreads()

def registerThread(thread):
    debug("Registering Thread")
    storage.threads.add(thread)

def registerClient(mbClient):
    storage.clients.add(mbClient)

def destroyThread(thread):
    debug("Destroying Thread")
    thread.stop()
    storage.threads.discard(thread)

def destroy_all_threads():
    global threads, clients
    debug("Killing all threads.")

    for thread in storage.threads:
        thread.stop()

    for client in storage.clients:
        client.syncThread = None

    storage.threads = set()
    storage.clients = set()

def clear_caches():
    pass

