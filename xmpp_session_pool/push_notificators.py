__author__ = 'kovtash'

import time
import logging
import urllib
import urllib2
from urllib2 import URLError, HTTPError
import json
import threading
from multiprocessing import Process
import os.path
import pyapns_client

class APNWSGINotification(threading.Thread):
    def __init__(self,host,app_id):
        if  host is None or app_id is None:
            raise ValueError
        self.push_url = os.path.join(host,app_id)

        self.notifications_available = threading.Condition()
        super(APNWSGINotification, self).__init__()
        self.keepRunning = True
        self.notifications=[]

    def run(self):
        while self.keepRunning:
            with self.notifications_available:
                self.notifications_available.wait()

            for i in xrange(len(self.notifications)):
                notification = self.notifications.pop(0)
                post_data = urllib.urlencode(notification)
                p = Process(target=self.send_notification, args=(post_data,))
                p.start()

    def send_notification(self,post_data):
        try:
            urllib2.urlopen(self.push_url,data=post_data)
        except URLError, HTTPError:
            logging.debug('%s : PushEvent :Push service response error',time.ctime())

    def stop(self):
        self.keepRunning = False
        with self.notifications_available:
            self.notifications_available.notify_all()

    def notify(self,token=None,message=None,unread_count=None):
        aps_message = {'aps':{'sound':'chime'}}
        if  message is not None and token is not None:
            if len(message) > 100:
                message = message[:97]+'...'
            aps_message['aps']['alert']=message
        else:
            return

        if unread_count is not None:
            aps_message['aps']['badge']=unread_count

        self.notifications.append({'token':token,'message':json.dumps(aps_message)})
        with self.notifications_available:
            self.notifications_available.notify_all()

class PyAPNSNotification():
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

    def stop(self):
        pass

    def notify(self,token=None,message=None,unread_count=None):
        aps_message = {'aps':{'sound':'chime'}}
        if  message is not None and token is not None:
            if len(message) > 100:
                message = message[:97]+'...'
            aps_message['aps']['alert']=message
        else:
            return

        if unread_count is not None:
            aps_message['aps']['badge']=unread_count

        pyapns_client.notify(self.app_id,token,aps_message,async=True)