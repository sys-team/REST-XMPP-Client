__author__ = 'kovtash'

from bottle_app import app
import inspect
import os
from xmpp_plugin import XMPPPlugin, PyAPNSNotification, APNWSGINotification

class BottleApp(object):
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

        self._app = app
        self._app.uninstall(XMPPPlugin)
        self._app.install(XMPPPlugin(debug=debug,push_sender=notification_sender))

    def run(self,host='0.0.0.0',port=5000):
        self._app.run(host=host, port=port, server='cherrypy')

    def stop(self):
        self._app.close()