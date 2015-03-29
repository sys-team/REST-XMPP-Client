# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

try:
    import ujson as json
except ImportError:
    import json


class BaseNotificator(object):
    def notify(self, token=None, message=None, unread_count=None,
               max_message_len=100, message_cut_end='...',
               contact_name=None, contact_id=None, sound=True):
        if token is None:
            return

        full_message = None
        if message is not None or contact_name is not None:
            full_message_parts = []
            if contact_name is not None:
                full_message_parts.append(contact_name)

                if message is not None:
                    full_message_parts.append(': ')

            if message is not None:
                full_message_parts.append(message)

            full_message = ''.join(full_message_parts)

        aps_message = {'aps': {}}

        if sound:
            aps_message['aps']['sound'] = 'chime'

        if full_message is not None:
            aps_message['aps']['alert'] = ''

        if unread_count is not None:
            aps_message['aps']['badge'] = unread_count

        if contact_id is not None:
            aps_message['im'] = {}
            aps_message['im']['contact_id'] = contact_id

        if full_message is not None:
            payload = json.dumps(aps_message, ensure_ascii=False).encode('utf-8')
            max_payload_len = 250 - len(payload)

            if len(full_message) > max_message_len:
                full_message = full_message[:max_message_len] + message_cut_end

            if len(full_message.encode('utf-8')) > max_payload_len:
                new_message_len = max_payload_len - len(message_cut_end)
                while len(full_message.encode('utf-8')) > new_message_len:
                    full_message = full_message[:-1]

                full_message = full_message + message_cut_end

            aps_message['aps']['alert'] = full_message

        self.perform_notification(token, aps_message)

    def perform_notification(self, token, aps_message):
        pass

    def start(self):
        pass

    def stop(self):
        pass
