__author__ = 'kovtash'

import logging
import urllib
import urllib2
from urllib2 import URLError, HTTPError
from Queue import Queue
import json
import threading
from multiprocessing import Process
import multiprocessing
import os.path
import pyapns_client
import time

class NotificationAbstract(object):
    def start(self):
        pass

    def stop(self):
        pass

    def notify(self, token=None, message=None, unread_count=None, max_message_len=100, message_cut_end='...', contact_name=None, contact_id=None, sound=True):
        if token is None:
            return

        full_message = None
        if  message is not None or contact_name is not None:
            full_message = ''
            if contact_name is not None:
                full_message = full_message.join([contact_name])

                if  message is not None:
                   full_message = full_message.join([': '])

            if  message is not None:
                full_message = full_message.join([message])

        aps_message = {'aps':{}}

        if  sound:
            aps_message['aps']['sound'] = 'chime'

        if  full_message is not None:
            aps_message['aps']['alert'] = ''

        if unread_count is not None:
            aps_message['aps']['badge'] = unread_count

        if contact_id is not None:
            aps_message['im'] = {}
            aps_message['im']['contact_id'] = contact_id

        payload = json.dumps(aps_message, separators = (',', ':'), ensure_ascii = False).encode('utf-8')
        max_payload_len = 250 - len(payload)

        if  full_message is not None:
            if  len(full_message) > max_message_len:
                full_message = full_message[:max_message_len] + message_cut_end

            if len(full_message.encode('utf-8')) > max_payload_len:
                new_message_len = max_payload_len - len(message_cut_end)
                while len(full_message.encode('utf-8')) > new_message_len:
                    full_message = full_message[:-1]

                full_message = full_message + message_cut_end

            aps_message['aps']['alert'] = full_message

        self.perform_notification(token, aps_message)

    def perform_notification(self, token, aps_message):
        pass


class APNWSGINotification(threading.Thread, NotificationAbstract):
    def __init__(self, host, app_id):
        if  host is None or app_id is None:
            raise ValueError
        self.push_url = os.path.join(host, app_id)
        super(APNWSGINotification, self).__init__()
        self.keepRunning = True
        self.notifications = Queue()

    def run(self):
        def send_notification(notification):
            post_data = urllib.urlencode(notification)
            try:
                urllib2.urlopen(self.push_url, data = post_data)
            except URLError, HTTPError:
                pass

        while self.keepRunning or not self.notifications.empty():
            notification = self.notifications.get()
            if notification is not None:
                p = Process(target = send_notification, args = (notification,))
                p.start()
                self.notifications.task_done()

    def stop(self):
        self.keepRunning = False
        self.notifications.put(None)
        for child_process in multiprocessing.active_children():
            if  child_process.is_alive():
                child_process.join(10)

    def perform_notification(self, token,aps_message):
        self.notifications.put({'token':token,'message':json.dumps(aps_message)})


class PyAPNSNotification(threading.Thread, NotificationAbstract):
    def __init__(self, host, app_id, cert_file, dev_mode = False, reconnect_interval=10):
        super(PyAPNSNotification, self).__init__()
        self.keepRunning = True
        self.is_server_ready = False
        self.notifications = Queue()
        pyapns_client.configure({'HOST': host})
        self.reconnect_interval = reconnect_interval
        self.app_id = app_id
        self.cert_file = cert_file
        if  dev_mode:
            self.mode = 'sandbox'
        else:
            self.mode = 'production'

    def run(self):
        while self.keepRunning or not self.notifications.empty():
            if not self.is_server_ready:
                try:
                    pyapns_client.provision(self.app_id, open(self.cert_file).read(), self.mode)
                    self.is_server_ready = True
                except Exception:
                    if self.keepRunning:
                        self.is_server_ready = False
                        time.sleep(self.reconnect_interval)
                        continue
                    else:
                        break

            notification = self.notifications.get()
            if notification is not None:
                try:
                    pyapns_client.notify(self.app_id, notification['token'], notification['message'])
                except Exception:
                    self.is_server_ready = False
                    self.notifications.put(notification)

                self.notifications.task_done()

    def stop(self):
        self.keepRunning = False
        self.notifications.put(None)

    def perform_notification(self, token, aps_message):
        self.notifications.put({'token':token,'message':aps_message})