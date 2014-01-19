# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import uuid
import logging
from Queue import Queue


class XMPPSession(object):
    def __init__(self, session_id, xmpp_client, im_client):
        self.session_id = session_id
        self.token = uuid.uuid4().hex
        self.im_client = im_client
        self.xmpp_client = xmpp_client
        self.xmpp_client.register_events_observer(self)
        self.notification_queue = Queue()
        if not self.xmpp_client.isConnected():
            self.xmpp_client.setup_connection()
        self.should_send_message_body = False

    def clean(self, with_notification=True):
        if with_notification:
            self.im_client.push_notification(message="Session closed. Login again, to start new session.")
        logging.debug(u'SessionEvent : Session %s start cleaning', self.xmpp_client.jid)
        self.im_client.session_closed(self)
        self.xmpp_client.unregister_events_observer(self)
        logging.debug(u'SessionEvent : Session %s cleaning done', self.xmpp_client.jid)

    def message_appended_notification(self, contact_id, message_text, inbound):
        contact = self.xmpp_client.contact(contact_id)

        if message_text is not None and contact is not None:
            self.notify_observers()
            if inbound:
                if self.should_send_message_body:
                    message_body = message_text
                else:
                    message_body = None
                self.im_client.push_notification(message=message_body, contact_name=contact['name'], contact_id=contact_id)

    def message_delivered_notification(self, contact_id, message_id):
        self.notify_observers()

    def contacts_updated_notification(self):
        self.notify_observers()

    def unread_count_updated_notification(self):
        self.im_client.push_notification(sound=False)

    @property
    def jid(self):
        return self.xmpp_client.jid.getStripped()

    @property
    def unread_count(self):
        return self.xmpp_client.unread_count

    def messages(self, contact_ids=None, event_offset=None):
        return self.xmpp_client.messages(contact_ids=contact_ids, event_offset=event_offset)

    def send(self, contact_id, message):
        return self.xmpp_client.send_message(contact_id=contact_id, message=message)

    def send_by_jid(self, jid, message):
        return self.xmpp_client.send_message_by_jid(jid=jid, message=message)

    def contacts(self, event_offset=None):
        return self.xmpp_client.contacts(event_offset=event_offset)

    def contact(self, contact_id):
        contact = self.xmpp_client.contact(contact_id)
        if contact is None:
            raise KeyError
        return contact

    def add_contact(self, jid, name=None, groups=[]):
        return self.xmpp_client.add_contact(jid=jid, name=name, groups=groups)

    def update_contact(self, contact_id, name=None, groups=None):
        self.xmpp_client.update_contact(contact_id=contact_id, name=name, groups=groups)

    def set_contact_read_offset(self, contact_id, read_offset):
        self.xmpp_client.set_contact_read_offset(contact_id=contact_id, read_offset=read_offset)

    def set_contact_authorization(self, contact_id, authorization):
        self.xmpp_client.set_contact_authorization(contact_id=contact_id, authorization=authorization)

    def contact_by_jid(self, jid):
        return self.xmpp_client.contact_by_jid(jid=jid)

    def remove_contact(self, contact_id):
        self.xmpp_client.remove_contact(contact_id=contact_id)

    def muc(self, muc_id):
        return self.xmpp_client.muc(muc_id=muc_id)

    def create_muc(self, muc_node, name):
        self.xmpp_client.create_muc(muc_node=muc_node, name=name)

    def muc_by_node(self, muc_node):
        return self.xmpp_client.muc_by_node(muc_node=muc_node)

    def remove_muc(self, muc_id):
        return self.xmpp_client.remove_muc(muc_id=muc_id)

    def update_muc(self, muc_id, name=None, members=None):
        self.xmpp_client.update_muc(muc_id=muc_id, name=name, members=members)

    def set_muc_read_offset(self, muc_id, read_offset):
        self.xmpp_client.set_muc_read_offset(muc_id=muc_id, read_offset=read_offset)

    def wait_for_notification(self, callback):
        self.notification_queue.put_nowait(callback)

    def notify_observers(self):
        notification_queue = self.notification_queue
        while not notification_queue.empty():
            callback = notification_queue.get_nowait()
            callback()
            notification_queue.task_done()
