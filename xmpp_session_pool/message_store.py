# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time
from xmpp.client import PlugIn

class XMPPMessagesStore(PlugIn):
    def __init__(self,id_generator,max_message_size = 512, chat_buffer_size=50):
        PlugIn.__init__(self)
        self.id_generator = id_generator
        self.max_message_size = max_message_size
        self.chat_buffer_size = chat_buffer_size
        self.chats_store = {}
        self.DBG_LINE='message_store'

    def plugin(self,owner):
        """ Register presence and subscription trackers in the owner's dispatcher.
       Also request roster from server if the 'request' argument is set.
       Used internally."""
        self._owner.Dispatcher.RegisterHandler('message',self.xmpp_message_handler)

    def xmpp_message_handler(self, con, event):
        jid_from = event.getFrom().getStripped()
        contact_id = self._owner.getRoster().itemId(jid_from)
        contact = self._owner.getRoster().getItem(contact_id)
        message_text = event.getBody()

        if  message_text is not None and contact is not None:
            self.append_message(contact_id=contact_id,inbound=True,text=message_text)

    def append_message(self,contact_id,inbound,text):
        if contact_id not in self.chats_store:
            self.chats_store[contact_id] = []

        messages = []
        event_id = self.id_generator.id()
        timestamp = time.time()
        for i in xrange(0, len(text), self.max_message_size):
            messages.append({'event_id':event_id,
                             'inbound':inbound,
                             'text':text[i:i+self.max_message_size],
                             'timestamp':timestamp,
                             'contact_id':contact_id,
                             'chunk_id': i
            })

        for message in messages:
            self.chats_store[contact_id].append(message)

        if len(self.chats_store[contact_id]) > self.chat_buffer_size:
            for i in xrange (0,len(self.chats_store[contact_id])-self.chat_buffer_size):
                del self.chats_store[contact_id][0]

        return messages

    def messages(self,contact_ids=None, event_offset=None):
        result = []
        if contact_ids is None:
            for chat in self.chats_store.values():
                result+=chat
        else:
            for jid in self.chats_store.iterkeys():
                if jid in contact_ids:
                    result += self.chats_store[jid]

        if event_offset is not None:
            result = filter(lambda message: message['event_id'] > event_offset,result)

        return result

    def all_messages(self):
        return self.chats_store

    def remove_messages_for_contact(self,contact_id):
        if contact_id in self.chats_store:
            del self.chats_store[contact_id]
