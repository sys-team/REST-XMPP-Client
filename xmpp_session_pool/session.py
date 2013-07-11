# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
import xmpp
import logging
import threading
from  notificators import XMPPPollNotification

class XMPPSession(object):
    def __init__(self,client,push_token=None,push_sender=None):
        self.token = uuid.uuid4().hex
        self.push_sender = push_sender
        self.push_token = push_token
        self.poll_notifier = XMPPPollNotification()
        self.client = client
        self.client.register_events_observer(self)
        if not self.client.isConnected():
            self.client.setup_connection()

    def clean(self,with_notification=True):
        if   with_notification:
            self.push_sender.notify(token=self.push_token,message="Session closed. Login again, to start new session.",unread_count=0)
        logging.debug(u'SessionEvent : Session %s start cleaning',self.client.jid)
        self.client.unregister_events_observer(self)
        self.poll_notifier.stop()
        logging.debug(u'SessionEvent : Session %s cleaning done', self.client.jid)

    def message_appended_notification(self,contact_id,message_text,inbound):
        contact = self.client.contact(contact_id)

        if  message_text is not None and contact is not None:
            self.poll_notifier.notify()
            if self.push_sender is not None and inbound:
                self.push_sender.notify(token=self.push_token,message=None,unread_count=self.client.unread_count(),contact_name=contact['name'],contact_id=contact_id)

    def contacts_updated_notification(self):
        self.poll_notifier.notify()

    def unread_count_updated_notification(self):
        self.poll_notifier.notify()
        self.push_sender.notify(token=self.push_token,unread_count=self.client.unread_count(),sound=False)

    @property
    def jid(self):
        return self.client.jid.getStripped()

    def messages(self,contact_ids=None,event_offset=None):
        return self.client.messages(contact_ids=contact_ids,event_offset=event_offset)

    def send(self,contact_id,message):
        return self.client.send_message(contact_id=contact_id,message=message)

    def send_by_jid(self,jid,message):
        return self.client.send_message_by_jid(jid=jid,message=message)

    def contacts(self,event_offset=None):
        return self.client.contacts(event_offset=event_offset)

    def contact(self,contact_id):
        contact = self.client.contact(contact_id)
        if  contact is None:
            raise KeyError
        return contact

    def add_contact(self,jid,name=None,groups=[]):
        self.client.add_contact(jid=jid,name=name,groups=groups)

    def update_contact(self,contact_id,name=None,groups=None):
        self.client.update_contact(contact_id=contact_id,name=name,groups=groups)

    def set_contact_read_offset(self,contact_id,read_offset):
        self.client.set_contact_read_offset(contact_id=contact_id,read_offset=read_offset)

    def set_contact_authorization(self,contact_id,authorization):
        self.client.set_contact_authorization(contact_id=contact_id,authorization=authorization)

    def contact_by_jid(self,jid):
        self.client.contact_by_jid(jid=jid)

    def remove_contact(self,contact_id):
        self.client.remove_contact(contact_id=contact_id)

    def poll_changes(self):
        return self.poll_notifier.poll()

class XMPPClientThread(threading.Thread):
    """Threaded XMPP client"""
    def __init__(self, client):
        super(XMPPClientThread, self).__init__()
        self.client = client
        self.client.setup_connection()
        self.keepRunning = True

    def run(self):
        while self.keepRunning:
            try:
                self.client.Process(1)
            except xmpp.protocol.StreamError:
                self.client.disconnect()

        self.client.disconnect()

    def stop(self):
        self.keepRunning = False