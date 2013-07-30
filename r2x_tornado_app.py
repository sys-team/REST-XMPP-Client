__author__ = 'kovtash'

import inspect
import os
from xmpp_session_pool import XMPPSessionPool, PyAPNSNotification, APNWSGINotification
from concurrent import futures
import tornado.ioloop
import tornado.web
from tornado_app import MainHandler, StartSession

class TornadoApp(object):
    def __init__(self,debug=False,push_app_id='im',
                 push_dev_mode=False,push_notification_sender='apnwsgi',
                 push_server_address=None,push_cert_dir='certificates'):
        notification_sender = None
        if  push_server_address is not None:
            if  push_notification_sender == 'pyapns':
                current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
                cert_file = os.path.join(current_dir,push_cert_dir,push_app_id+'.pem')
                notification_sender = PyAPNSNotification(host=push_server_address,app_id=push_app_id,cert_file=cert_file,dev_mode=push_dev_mode)
            elif push_notification_sender == 'apnwsgi':
                notification_sender = APNWSGINotification(host=push_server_address,app_id=push_app_id)

        self._xmpp_session_pool = XMPPSessionPool(debug=debug,push_sender=notification_sender)
        self._async_worker = futures.ThreadPoolExecutor(max_workers=10)
        self._app = tornado.web.Application([
            (r"/", MainHandler,dict(async_worker = self._async_worker)),
            (r"/start-session", StartSession,dict(session_pool = self._xmpp_session_pool, async_worker = self._async_worker))
        ])

    def run(self,host='0.0.0.0',port=5000):
        self._app.listen(port)
        tornado.ioloop.IOLoop.instance().start()

    def stop(self):
        self._xmpp_session_pool.clean()