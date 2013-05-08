# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import logging
from app_builder import make_app

port = 5000
host = '0.0.0.0'
dev_mode = False

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app = make_app(dev_mode=dev_mode,push_notification_sender='apnwsgi')
    app.run(host=host, port=port, server='cherrypy') #reloader=True
    app.close()
