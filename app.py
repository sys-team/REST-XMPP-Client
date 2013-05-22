# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import logging
from app_builder import make_app
import signal

port = 5000
host = '0.0.0.0'
dev_mode = False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app = make_app(dev_mode=dev_mode,push_notification_sender='apnwsgi')

    def term_handler(signum = None, frame = None):
        logging.info('Application termination started')
        app.close()
        logging.info('Application terminated')

    signal.signal(signal.SIGTERM, term_handler)

    app.run(host=host, port=port, server='cherrypy') #reloader=True
    app.close()
