# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time
import logging
import urllib
import urllib2
from urllib2 import URLError, HTTPError
import json
import threading
from multiprocessing import Process

class XMPPPollNotification():
    def __init__(self,timeout=60,poll_interval=1):
        self.is_notification_available = threading.Condition()
        self.poller_pool = []
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.keepRunning = True

    def poll(self):
        self.is_notification_available.acquire()
        start_time = time.time()
        if self.keepRunning:
            self.is_notification_available.wait(self.timeout+1)
        self.is_notification_available.release()
        waiting_time = time.time()-start_time
        if waiting_time > self.timeout or not self.keepRunning:
            return False
        else:
            return True

    def notify(self):
        self.is_notification_available.acquire()
        self.is_notification_available.notify_all()
        self.is_notification_available.release()

    def stop(self):
        self.keepRunning = False
        self.notify()

class XMPPPushNotification(threading.Thread):
    def __init__(self,push_token):
        if  push_token is None:
            raise ValueError

        self.notification_lock = threading.Lock()
        self.push_token = push_token
        super(XMPPPushNotification, self).__init__()
        self.keepRunning = True
        self.notifications=[]
        self.start()

    def run(self):
        while self.keepRunning:
            self.notification_lock.acquire()
            for i in xrange(len(self.notifications)):
                notification = self.notifications.pop(0)
                post_data = urllib.urlencode({'token':self.push_token,'message':json.dumps(notification)})
                p = Process(target=self.send_notification, args=(post_data,))
                p.start()
                p.join()

    def send_notification(self,post_data):
        try:
            urllib2.urlopen('https://apns-aws.unact.ru/im-dev',data=post_data)
        except URLError, HTTPError:
            logging.debug('%s : PushEvent :Push service response error',time.ctime())
            #self.notifications.append(notification)

    def stop(self):
        self.keepRunning = False
        self.notification_lock.acquire(False)
        self.notification_lock.release()

    def notify(self,message=None,unread_count=None):
        notification = {'aps':{'sound':'chime'}}
        if  message is not None:
            if len(message) > 100:
                message = message[:97]+'...'
            notification['aps']['alert']=message

        if unread_count is not None:
            notification['aps']['badge']=unread_count

        self.notification_lock.acquire(False)
        self.notifications.append(notification)
        self.notification_lock.release()