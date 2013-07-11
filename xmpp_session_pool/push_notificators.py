__author__ = 'kovtash'

import time
import logging
import urllib
import urllib2
from urllib2 import URLError, HTTPError
import json
import threading
from multiprocessing import Process
import multiprocessing
import os.path
import pyapns_client

class NotificationAbstract():
    def start(self):
        pass

    def stop(self):
        pass

    def notify(self,token=None,message=None,unread_count=None,max_message_len=100,message_cut_end='...',contact_name=None,contact_id=None,sound=True):
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
            aps_message['aps']['alert']=''

        if unread_count is not None:
            aps_message['aps']['badge']=unread_count

        if contact_id is not None:
            aps_message['im']={}
            aps_message['im']['contact_id']=contact_id

        payload = json.dumps(aps_message,separators=(',',':'), ensure_ascii=False).encode('utf-8')
        max_payload_len = 250 - len(payload)

        if  full_message is not None:
            if  len(full_message) > max_message_len:
                full_message = full_message[:max_message_len] + message_cut_end

            if len(full_message.encode('utf-8')) > max_payload_len:
                new_message_len = max_payload_len - len(message_cut_end)
                while len(full_message.encode('utf-8')) > new_message_len:
                    full_message = full_message[:-1]

                full_message = full_message + message_cut_end

            aps_message['aps']['alert']=full_message

        self.perform_notification(token,aps_message)
        print(aps_message)

    def perform_notification(self,token,aps_message):
        pass


class APNWSGINotification(threading.Thread, NotificationAbstract):
    def __init__(self,host,app_id):
        if  host is None or app_id is None:
            raise ValueError
        self.push_url = os.path.join(host,app_id)

        self.notifications_available = threading.Condition()
        self.notifications_lock = threading.Lock()
        super(APNWSGINotification, self).__init__()
        self.keepRunning = True
        self.notifications=[]

    def run(self):
        def send_notification(notification):
            post_data = urllib.urlencode(notification)
            try:
                urllib2.urlopen(self.push_url,data=post_data)
            except URLError, HTTPError:
                pass

        while self.keepRunning:
            with self.notifications_available:
                self.notifications_available.wait()

            with self.notifications_lock:
                for i in xrange(len(self.notifications)):
                    notification = self.notifications.pop(0)
                    p = Process(target=send_notification, args=(notification,))
                    p.start()

    def stop(self):
        self.keepRunning = False
        with self.notifications_available:
            self.notifications_available.notify_all()

        for child_process in multiprocessing.active_children():
            if  child_process.is_alive():
                child_process.join(10)

    def perform_notification(self,token,aps_message):
        with self.notifications_lock:
            self.notifications.append({'token':token,'message':json.dumps(aps_message)})
        with self.notifications_available:
            self.notifications_available.notify_all()


class PyAPNSNotification(NotificationAbstract):
    def __init__(self,host,app_id,cert_file,dev_mode=False):
        pyapns_client.configure({'HOST': host})
        self.app_id = app_id
        self.cert_file = cert_file
        self.dev_mode = dev_mode

    def start(self):
        if  self.dev_mode:
            mode = 'sandbox'
        else:
            mode = 'production'

        pyapns_client.provision(self.app_id,open(self.cert_file).read(), mode)

    def perform_notification(self,token,aps_message):
        pyapns_client.notify(self.app_id,token,aps_message,async=True)