# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

from xmpp_session_pool import BaseNotificator
from Queue import Queue
import threading
import pyapns_client
import time
import logging


logger = logging.getLogger('PyAPNSNotificator')


class PyAPNSNotificator(threading.Thread, BaseNotificator):
    def __init__(self, host, cert_file, app_id, dev_mode=False,
                 reconnect_interval=10, chunk_size=10):
        super(PyAPNSNotificator, self).__init__()
        self.keepRunning = True
        self.is_server_ready = False
        self.notifications = Queue()
        pyapns_client.configure({'HOST': host})
        self.reconnect_interval = reconnect_interval
        self.app_id = app_id
        self.cert_file = cert_file
        self.chunk_size = chunk_size
        if dev_mode:
            self.mode = 'sandbox'
        else:
            self.mode = 'production'

    def run(self):
        logger.info("Started")
        while self.keepRunning or not self.notifications.empty():
            if not self.is_server_ready:
                try:
                    logger.info('Trying to connect to PyAPNS')
                    pyapns_client.provision(self.app_id, open(self.cert_file).read(), self.mode)
                    self.is_server_ready = True
                except Exception as exception:
                    logger.error('PyAPNS connection error')
                    logger.exception(exception)
                    if self.keepRunning:
                        self.is_server_ready = False
                        time.sleep(self.reconnect_interval)
                        continue
                    else:
                        break

            tokens = []
            messages = []
            for i in xrange(self.chunk_size):
                if self.notifications.empty() and len(tokens):
                    break

                notification = self.notifications.get()

                if notification is None:
                    self.notifications.task_done()
                    break

                tokens.append(notification['token'])
                messages.append(notification['message'])
                self.notifications.task_done()

            try:
                if len(tokens):
                    pyapns_client.notify(self.app_id, tokens, messages)
            except Exception as exception:
                logger.error('PyAPNS connection error')
                logger.exception(exception)
                self.is_server_ready = False
                for i in xrange(len(tokens)):
                    self.notifications.put({'token': tokens[i], 'message': messages[i]})

        logger.info('Thread finished')

    def stop(self):
        logger.info('Stopping')
        self.keepRunning = False
        self.notifications.put(None)

    def perform_notification(self, token, aps_message):
        self.notifications.put({'token': token, 'message': aps_message})
