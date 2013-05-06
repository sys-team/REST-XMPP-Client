# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import inspect
import xmpp_session_pool
from bottle import PluginError

class XMPPPlugin(object):

    name = 'xmpp_pool'
    api = 2

    def __init__(self,keyword = 'xmpp_pool',debug=False,push_sender=None):
        self.session_pool = xmpp_session_pool.XMPPSessionPool(debug=debug,push_sender=push_sender)
        self.keyword = keyword

    def setup(self, app):
        """ Make sure that other installed plugins don't affect the same
            keyword argument."""
        for other in app.plugins:
            if not isinstance(other, XMPPPlugin): continue
            if other.keyword == self.keyword:
                raise PluginError("Found another %s plugin with conflicting settings (non-unique keyword).",self.name)

    def apply(self, callback, context):
        # Override global configuration with route-specific values.
        conf = context.config.get('xmpp_pool') or {}
        keyword = conf.get('keyword', self.keyword)

        # Test if the original callback accepts a 'db' keyword.
        # Ignore it if it does not need a database handle.
        args = inspect.getargspec(context.callback)[0]
        if keyword not in args:
            return callback

        def wrapper(*args, **kwargs):
            kwargs[keyword] = self.session_pool

            rv = callback(*args, **kwargs)
            return rv

        # Replace the route callback with the wrapped one.
        return wrapper

    def close(self):
        self.session_pool.clean()