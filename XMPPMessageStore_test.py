# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

from xmpp_session_pool import XMPPMessagesStore

store = XMPPMessagesStore()

def append_message_test():
    jids = ['1@jabber','2@jabber','3@jabber']

    for jid in jids:
        message_number = 0
        for i in range(0,20):
            message_number+=1
            store.append_message(jid,message_number%2,jid+'-'+str(message_number),'some text')

    print 'append_message_test OK'

def all_messages_test():
    messages_count = len(store.messages())

    if messages_count != 60:
        print 'all_messages_test Fail',messages_count

    print 'all_messages_test OK'

def messages_filters_test():
    messages = store.messages(jids=('2@jabber','1@jabber'))
    messages = sorted(messages, key=lambda x: x['timestamp'])
    timestamp = messages[9]['timestamp']

    messages_count = len(store.messages(jids=['2@jabber','1@jabber'],timestamp=timestamp))

    if messages_count != 30:
        print 'messages_filters_test Fail',messages_count

    print 'messages_filters_test OK'

def messages_by_jid_test():
    result = store.messages_by_jid()

    if len(result.keys()) != 3:
        print 'messages_by_jid_test Failed - wrong keys number'

    messages_count = 0
    for jid in result.iterkeys():
        messages_count += len(result[jid])

    if messages_count != 60:
        print 'messages_by_jid_test Failed - wrong messages number'

    test_timestamp = result['2@jabber'][4]['timestamp']
    result = store.messages_by_jid(timestamp=test_timestamp)

    if len(result.keys()) != 3:
        print 'messages_by_jid_test Failed - wrong keys number'

    if len(result['1@jabber']) != 0:
        print 'messages_by_jid_test Failed - wrong messages number for 1@jabber'

    if len(result['2@jabber']) != 15:
        print 'messages_by_jid_test Failed - wrong messages number for 1@jabber'

    if len(result['3@jabber']) != 20:
        print 'messages_by_jid_test Failed - wrong messages number for 1@jabber'

    print 'messages_by_jid_test OK'


append_message_test()
all_messages_test()
messages_filters_test()
messages_by_jid_test()
