# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time

class XMPPMessagesStore():
    def __init__(self,max_message_size = 512, chat_buffer_size=50):
        self.max_message_size = max_message_size
        self.chat_buffer_size = chat_buffer_size
        self.chats_store = {}

    def append_message(self,contact_id,inbound,event_id,text):
        if contact_id not in self.chats_store:
            self.chats_store[contact_id] = []

        messages = []

        for i in xrange(0, len(text), self.max_message_size):
            messages.append({'event_id':event_id,
                             'inbound':inbound,
                             'text':text[i:i+self.max_message_size],
                             'timestamp':time.time(),
                             'contact_id':contact_id
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

    def remove_messages_for_conatct(self,contact_id):
        if contact_id in self.chats_store:
            del self.chats_store[contact_id]
