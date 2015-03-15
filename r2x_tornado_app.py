__author__ = 'kovtash'

import uuid
import tornado.ioloop
import tornado.web
import concurrent
from xmpp_session_pool import XMPPSessionPool
from tornado_app import MainHandler, StartSession, SessionHandler, SessionContactsHandler,\
    SessionMessagesHandler, SessionFeedHandler, SessionNotificationHandler, ContactHandler,\
    ContactMessagesHandler, ServerStatusHandler, SessionMUCsHandler, MucHandler, MucMessagesHandler


class TornadoApp(object):
    def __init__(self, debug=False, push_sender=None, admin_token_hash=None):

        self._xmpp_session_pool = XMPPSessionPool(debug=debug, push_sender=push_sender)
        self._async_worker = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        if admin_token_hash is None:
            admin_token_hash = "".join([uuid.uuid4().get_hex(), uuid.uuid4().get_hex()])
        elif len(admin_token_hash) != 64:
            raise ValueError('admin_token_hash argument must be a hexadecimal string\
 64 characters length')

        tornado_conf = dict(session_pool=self._xmpp_session_pool, async_worker=self._async_worker,
                            admin_token_hash=admin_token_hash)
        self._app = tornado.web.Application([
            (r"/sessions/([^/]*)/notification", SessionNotificationHandler, tornado_conf),
            (r"/sessions/([^/]*)/feed", SessionFeedHandler, tornado_conf),
            (r"/sessions/([^/]*)/mucs", SessionMUCsHandler, tornado_conf),
            (r"/sessions/([^/]*)/mucs/([^/]*)", MucHandler, tornado_conf),
            (r"/sessions/([^/]*)/mucs/([^/]*)/messages", MucMessagesHandler, tornado_conf),
            (r"/sessions/([^/]*)/contacts", SessionContactsHandler, tornado_conf),
            (r"/sessions/([^/]*)/contacts/([^/]*)", ContactHandler, tornado_conf),
            (r"/sessions/([^/]*)/contacts/([^/]*)/messages", ContactMessagesHandler, tornado_conf),
            (r"/sessions/([^/]*)/messages", SessionMessagesHandler, tornado_conf),
            (r"/sessions/([^/]*)", SessionHandler, tornado_conf),
            (r"/start-session", StartSession, tornado_conf),
            (r"/server-status", ServerStatusHandler, tornado_conf),
            (r"/", MainHandler)
        ])

    def run(self, port=5000, address=""):
        self._app.listen(port, address=address)
        tornado.ioloop.IOLoop.instance().start()

    def stop(self):
        self._xmpp_session_pool.clean()
