## Sublime TextSync

### Demo
[![YouTube Demo](./media/thumb3.jpg)](https://www.youtube.com/watch?v=MucOaGhCwp0)

- **Place this directory in the sublime packages directory**
- **See ex/textsync.settings for repo config**
- **If you have problems, open the console to check for errors** View > Show Console

ex/ should be synced in Sublime Text 3 between multiple clients if they are using the same TextSync server. "Ghost cursors" should also appear to indicate remote clients' cursor positioning.

To run the server, you can either put the contents of the server/ folder on Appengine, or you can run it as a development server with:

```
dev_appserver.py app.yaml
```