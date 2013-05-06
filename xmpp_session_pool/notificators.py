# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time
import threading

class XMPPPollNotification():
    def __init__(self,timeout=60):
        self.is_notification_available = threading.Condition()
        self.poller_pool = []
        self.timeout = timeout
        self.keepRunning = True

    def poll(self):
        start_time = time.time()
        with self.is_notification_available:
            self.is_notification_available.wait(self.timeout+1)
        waiting_time = time.time()-start_time
        if waiting_time > self.timeout or not self.keepRunning:
            return False
        else:
            return True

    def notify(self):
        with self.is_notification_available:
            self.is_notification_available.notify_all()

    def stop(self):
        self.keepRunning = False
        self.notify()