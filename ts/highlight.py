import sublime, json, time
from datetime import datetime
from threading import Thread

REGION_KEY = "textsync-cursor"
CURSOR_TIMEOUT = 7

UNDERLINE_FLAGS = sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_EMPTY_AS_OVERWRITE

MARK_STYLES = {
    'outline': sublime.DRAW_NO_FILL,
    'fill': sublime.DRAW_NO_OUTLINE,
    'solid underline': sublime.DRAW_SOLID_UNDERLINE | UNDERLINE_FLAGS,
    'squiggly underline': sublime.DRAW_SQUIGGLY_UNDERLINE | UNDERLINE_FLAGS,
    'stippled underline': sublime.DRAW_STIPPLED_UNDERLINE | UNDERLINE_FLAGS
}

MARK_SCOPE_FORMAT = 'string'

class GhostCursorSet:
    def __init__(self, shareObj):
        self.cursors = {}
        self.shareObj = shareObj
        self.view = shareObj.view
        self.refreshThread = SyncThread(self)
        self.refreshThread.start()

    def draw(self):
        """  Draw all cursors. First check for outdated cursors, then clear and redraw.  """

        if not self.cursors:
            return

        outdated = []

        for user_hash in self.cursors:
            if self.cursors[ user_hash ].isOutdated():
                outdated.append(user_hash)

        self.clear()

        for user_hash in outdated:
            del self.cursors[ user_hash ]

        for user_hash in self.cursors:
            self.cursors[user_hash].draw( self.view )

    def clear(self):
        """  Clear all visible cursors  """

        for user_hash in self.cursors:
            self.cursors[user_hash].clear( self.view )

    def handle_message(self, message):
        if self.shareObj.persist.settings.get("ghost_cursor") == None:
            return # bail if not enabled
        """  Handles incoming cursor messages from mobwrite  """

        message = json.loads( message )

        # print('handling messagex', type(message), message )

        for user_hash in message:
            cursor = self.getGhostCursor(user_hash)
            cursor.update( message[user_hash] )

        self.draw()

    def getGhostCursor(self, user_hash):
        if not user_hash in self.cursors:
            self.cursors[user_hash] = GhostCursor(user_hash, self.shareObj.persist.settings.get("ghost_cursor"))

        return self.cursors[user_hash]

    def terminate(self):
        self.refreshThread.stop()

class GhostCursor:
    def __init__(self, user_hash, mark_style):
        self.user_hash = user_hash
        self.marks = []
        if mark_style in MARK_STYLES:
            self.mark_style = mark_style
        else:
            self.mark_style = 'outline'
        self.mark_flags = MARK_STYLES[self.mark_style]
        self.lastUpdate = datetime.now()

    def key(self):
        return REGION_KEY + self.user_hash

    def regions(self):
        """  Returns a list of sublime regions, one for each ghost cursor  """
        
        regions = []

        for mark in self.marks:
            start = mark[0]
            end = mark[1]
            if abs( mark[1] - mark[0] ) < 1:
                end += 1
            regions.append( sublime.Region( start, end ) )

        return regions

    def draw(self, view):
        """  Draw the ghost cursor  """

        # draw_ghost_cursors = persist.settings.get('draw_ghost_cursors')
        draw_ghost_cursors = True

        if draw_ghost_cursors and self.marks:
            view.add_regions(
                self.key(),
                self.regions(),
                # '#FF0000',
                MARK_SCOPE_FORMAT, # need to figure out color
                flags=self.mark_flags
            )

    def clear(self, view):
        """  Remove all regions from this view  """
        
        view.erase_regions( self.key() )

    def reset(self):
        """  Clear the marks maintained by this object.

             Does not clear makes, just the references.
             The marks will be cleared on the next draw.
        """
        
        del self.marks[:]

    def update(self, message):
        self.lastUpdate = datetime.now()
        if "selection" in message:
            self.marks = message['selection']

    def isOutdated(self):
        currentTime = datetime.now()
        dt = currentTime - self.lastUpdate
        return dt.total_seconds() > CURSOR_TIMEOUT

class SyncThread(Thread):
    def __init__(self, GCset):
        super().__init__()

        self.isStopped = False
        self.GCset = GCset
        self.syncInterval = 2000

        self.GCset.shareObj.persist.registerThread(self)

    def stop(self):
        self.isStopped = True

    def run(self):
        # refresh cursors periodically. Allows cursors to go away after the corresponding client disconnects.
        while self.GCset.shareObj and not self.isStopped:
            self.GCset.draw() 
            time.sleep( self.syncInterval / 1000 )


