#!/usr/bin/python2.4

"""MobWrite - Real-time Synchronization and Collaboration Service

Copyright 2008 Google Inc.
http://code.google.com/p/google-mobwrite/

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

"""This file is the server, running under Google App Engine.

Accepting synchronization sessions from clients.
"""

__author__ = "fraser@google.com (Neil Fraser)"

import cgi
import sys
import webapp2

# sys.path.insert(0, "lib")
import mobwrite_core
from request_handler import Handler
# del sys.path[0]
import webapp2

mobwrite_core.CFG.initConfig("mobwrite_config.txt")
mobwrite = Handler()

class MainPage(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write('Hello, World!')
	def post(self):
		text = self.request.get('query')
		response = mobwrite.handleRequest( text ) + '\n\n'
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write( response )

app = webapp2.WSGIApplication([
	('/', MainPage),
], debug=True)

