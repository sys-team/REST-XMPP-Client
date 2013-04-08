# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import time

class XMPPMessagesStore():
    def __init__(self,max_message_size = 512, chat_buffer_size=50):
        self.max_message_size = max_message_size
        self.chat_buffer_size = chat_buffer_size
        self.chats_store = {}

    def append_message(self,jid,inbound,id,text):
        if jid not in self.chats_store:
            self.chats_store[jid] = []

        messages = []

        for i in xrange(0, len(text), self.max_message_size):
            messages.append({'id':id,
                             'inbound':inbound,
                             'text':text[i:i+self.max_message_size],
                             'timestamp':time.time(),
                             'contact_id':jid
            })

        for message in messages:
            self.chats_store[jid].append(message)

        if len(self.chats_store[jid]) > self.chat_buffer_size:
            for i in xrange (0,len(self.chats_store[jid])-self.chat_buffer_size):
                del self.chats_store[jid][0]

        return messages

    def messages(self,jids=None, timestamp=None):
        result = []
        if jids is None:
            for chat in self.chats_store.values():
                result+=chat
        else:
            for jid in self.chats_store.iterkeys():
                if jid in jids:
                    result += self.chats_store[jid]

        if timestamp is not None:
            result = filter(lambda message: message['timestamp'] > timestamp,result)

        return result

    def all_messages(self):
        return self.chats_store