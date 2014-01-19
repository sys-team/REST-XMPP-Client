# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time
from xmpp.client import PlugIn
import itertools


class XMPPMessagesStore(PlugIn):
    def __init__(self, id_generator, chat_buffer_size=50):
        PlugIn.__init__(self)
        self.id_generator = id_generator
        self.chat_buffer_size = chat_buffer_size
        self.chats_store = {}
        self.DBG_LINE = 'message_store'

    def plugin(self, owner):
        """ Register presence and subscription trackers in the owner's dispatcher.
       Also request roster from server if the 'request' argument is set.
       Used internally."""
        self._owner.Dispatcher.RegisterHandler('message', self.xmpp_message_handler, makefirst=True)
        self._owner.Dispatcher.RegisterHandler('message', self.xmpp_delivery_status_handler, ns='urn:xmpp:receipts',
                                               makefirst=True)

    def xmpp_message_handler(self, con, event):
        message_text = event.getBody()
        if message_text is None:
            return

        jid_from = event.getFrom().getStripped()
        contact_id = self._owner.getRoster().itemId(jid_from)
        contact = self._owner.getRoster().getItem(contact_id)
        if contact is None:
            return

        message_id = event.getID()
        if message_id is None:
            message_id = self.id_generator.id()

        delivery_receipt_asked = False
        if event.getID() is not None and event.getTag('request') is not None:
            delivery_receipt_asked = True

        self.append_message(contact_id=contact_id, inbound=True, text=message_text, message_id=message_id,
                            delivery_receipt_asked=delivery_receipt_asked)

    def xmpp_delivery_status_handler(self, con, event):
        received = event.getTag('received')
        if received is not None:
            message_id = received.getAttr('id')
            jid_from = event.getFrom().getStripped()
            contact_id = self._owner.getRoster().itemId(jid_from)
            if message_id is not None and contact_id in self.chats_store:
                for message in self.chats_store[contact_id]:
                    if not message['inbound'] and message['message_id'] == message_id:
                        message['delivered'] = True
                        message['event_id'] = self.id_generator.id()

    def append_message(self, contact_id, inbound, text, message_id = None, delivery_receipt_asked=False):
        if contact_id not in self.chats_store:
            self.chats_store[contact_id] = []

        messages = []
        event_id = self.id_generator.id()
        timestamp = time.time()

        messages.append({'event_id': event_id,
                         'inbound': inbound,
                         'text': text,
                         'timestamp': timestamp,
                         'contact_id': contact_id,
                         'message_id': message_id,
                         'delivered': False,
                         'delivery_receipt_asked': delivery_receipt_asked
        })

        for message in messages:
            self.chats_store[contact_id].append(message)

        if len(self.chats_store[contact_id]) > self.chat_buffer_size:
            for i in xrange(0, len(self.chats_store[contact_id]) - self.chat_buffer_size):
                del self.chats_store[contact_id][0]

        return messages

    def messages(self, contact_ids=None, event_offset=None):
        chat_store = self.chats_store
        if contact_ids is None:
            result = list(itertools.chain.from_iterable(chat_store.values()))
        else:
            result = []
            for jid in contact_ids:
                if jid in chat_store:
                    result += chat_store[jid]

        if event_offset is not None:
            result = filter(lambda message: message['event_id'] > event_offset, result)

        for message in result:
            if message['inbound'] and message['delivery_receipt_asked'] and not message['delivered']:
                self._owner.send_message_delivery_receipt(message['contact_id'], message['message_id'])
                message['delivered']=True

        return result

    def all_messages(self):
        return self.chats_store.copy()

    def remove_messages_for_contact(self, contact_id):
        if contact_id in self.chats_store:
            del self.chats_store[contact_id]
