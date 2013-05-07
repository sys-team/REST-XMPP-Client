__author__ = 'kovtash'

from rest2xmpp import app
import inspect
import os
from xmpp_plugin import XMPPPlugin, PyAPNSNotification, APNWSGINotification

def make_app(app_id='im',dev_mode=False,push_notification_sender='pyapns'):
    push_app_id = app_id
    if dev_mode:
        push_app_id = push_app_id+'-dev'

    notification_sender = None
    if  push_notification_sender == 'pyapns':
        current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        cert_file = os.path.join(current_dir,'certificates',push_app_id+'.pem')
        notification_sender = PyAPNSNotification(host='https://pyapns.unact.ru/',app_id=push_app_id,cert_file=cert_file,dev_mode=dev_mode)
    elif push_notification_sender == 'apnwsgi':
        notification_sender = APNWSGINotification(host='https://apns-aws.unact.ru',app_id=push_app_id)

    app.uninstall(XMPPPlugin)
    app.install(XMPPPlugin(debug=False,push_sender=notification_sender))

    return app