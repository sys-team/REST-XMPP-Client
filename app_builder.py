__author__ = 'kovtash'

from rest2xmpp import app
import inspect
import os
from xmpp_plugin import XMPPPlugin, PyAPNSNotification, APNWSGINotification

def make_app(debug=False,push_app_id='im',
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

    app.uninstall(XMPPPlugin)
    app.install(XMPPPlugin(debug=debug,push_sender=notification_sender))

    return app