__author__ = 'kovtash'

from tornado import web, gen, ioloop
from xmpp_session_pool import XMPPAuthError, XMPPConnectionError, XMPPSendError, digest
from datetime import timedelta
import json
import os
import uuid


AUTH_HEADER_PREFIX = 'Bearer '


def session_to_dict(session):
    return {
        'session_id': session.session_id,
        'jid': session.jid,
        'should_send_message_body': session.should_send_message_body,
        'start_timestamp': session.start_timestamp,
        'last_activity': session.last_activity,
        'push_token': session.im_client.push_token
    }


class MainHandler(web.RequestHandler):
    @gen.coroutine
    def head(self):
        pass


class XMPPClientHandler(web.RequestHandler):
    def initialize(self, session_pool, admin_token_hash, async_worker):
        self.session_pool = session_pool
        self.async_worker = async_worker
        self.response = {}

        if admin_token_hash is None:
            self.admin_token_hash = digest.digest(uuid.uuid4().hex)
        elif len(admin_token_hash) != digest.hex_digest_size():
            raise ValueError('admin_token_hash argument must be a hexadecimal string\
 %s characters length' % digest.hex_digest_size())
        else:
            self.admin_token_hash = admin_token_hash

    def write_error(self, status_code, **kwargs):
        self.write(self.response)

    def raise_value_error(self, parameter_name):
        self.response['error'] = {'code': 'XMPPServiceParametersError',
                                  'text': 'Parameter %s has wrong value' % parameter_name}
        raise web.HTTPError(400)

    def raise_message_sending_error(self):
        self.response['error'] = {'code': 'XMPPSendError', 'text': 'Message sending failed'}
        raise web.HTTPError(404)

    def raise_contact_error(self, contact_id):
        self.response['error'] = {'code': 'XMPPContactError',
                                  'text': 'There is no contact with id %s' % contact_id}
        raise web.HTTPError(404)

    def raise_muc_error(self, muc_id):
        self.response['error'] = {'code': 'XMPPContactError',
                                  'text': 'There is no MUC with id %s' % muc_id}
        raise web.HTTPError(404)

    def check_contact_id(self, contact_id):
        if contact_id is None:
            self.response['error'] = {'code': 'XMPPServiceParametersError',
                                      'text': 'Missing contact_id parameter'}
            raise web.HTTPError(400)

    def check_muc_id(self, muc_id):
        if muc_id is None:
            self.response['error'] = {'code': 'XMPPServiceParametersError',
                                      'text': 'Missing muc_id parameter'}
            raise web.HTTPError(400)

    def check_admin_access(self):
        if not digest.compare_digest(self.admin_token_hash, self.auth_token):
            self.response['error'] = {'code': 'XMPPAuthError', 'text': 'Wrong authorization data'}
            raise web.HTTPError(401)

    def get_header(self, header_name):
        if header_name in self.request.headers:
            return self.request.headers[header_name]
        else:
            return None

    def get_offset(self):
        offset = self.get_argument('offset', None)

        if offset is not None:
            try:
                offset = float(offset)
            except ValueError:
                self.raise_value_error('offset')

        return offset

    @property
    def should_wait(self):
        return self.get_argument('wait', None) is not None

    @property
    def should_expand(self):
        return self.get_argument('expand', None) is not None

    @property
    def auth_token(self):
        auth_header = self.get_header('Authorization')
        if auth_header is None:
            self.response['error'] = {'code': 'XMPPAuthError',
                                      'text': 'No authorization information provided'}
            raise web.HTTPError(502)

        prefix_len = len(AUTH_HEADER_PREFIX)
        prefix = auth_header[0:prefix_len]
        if prefix != AUTH_HEADER_PREFIX:
            self.response['error'] = {'code': 'XMPPAuthError',
                                      'text': 'Wrong header format'}
            raise web.HTTPError(502)

        return digest.digest(auth_header[prefix_len:])

    def get_session(self, session_id, accept_admin=False):
        self.response['session'] = {'session_id': session_id}

        if session_id is None:
            self.response['error'] = {'code': 'XMPPServiceParametersError',
                                      'text': 'Missing session_id parameter'}
            raise web.HTTPError(400)

        try:
            session = self.session_pool.session_for_id(session_id)
        except KeyError:
            self.response['error'] = {'code': 'XMPPSessionError',
                                      'text': 'There is no session with id %s' % session_id}
            raise web.HTTPError(404)

        if digest.compare_digest(self.auth_token, session.token):
            session.touch()
            return session
        elif accept_admin and digest.compare_digest(self.admin_token_hash, self.auth_token):
            return session
        else:
            self.response['error'] = {'code': 'XMPPAuthError', 'text': 'Wrong authorization data'}
            raise web.HTTPError(401)

    def get_body(self):
        if self.request.body is None:
            self.response['error'] = {'code': 'XMPPServiceParametersError',
                                      'text': 'Missing request body'}
            raise web.HTTPError(400)
        else:
            try:
                body = json.loads(self.request.body)
            except ValueError:
                self.response['error'] = {'code': 'XMPPServiceParametersError',
                                          'text': 'Not a valid JSON format'}
                raise web.HTTPError(400)
            return body


class StartSession(XMPPClientHandler):
    @gen.coroutine
    def post(self):
        jid = self.get_argument('jid', default=None)
        password = self.get_argument('password', default=None)
        server = self.get_argument('server', default=None)
        push_token = self.get_argument('push_token', default=None)
        client_id = self.get_argument('client_id', default=None)

        session_token = uuid.uuid4().hex
        session_token_hash = digest.digest(session_token)

        if jid is None or password is None or server is None:
            self.response['error'] = {'code': 'XMPPServiceParametersError',
                                      'text': 'Missing required parameters'}
            raise web.HTTPError(400)

        try:
            session_id = yield self.async_worker.submit(self.session_pool.start_session, jid=jid,
                                                        session_token=session_token_hash,
                                                        password=password, server=server,
                                                        push_token=push_token,
                                                        im_client_id=client_id)
            self.response['session'] = {'session_id': session_id}
        except XMPPAuthError:
            self.response['error'] = \
                {'code': 'XMPPUpstreamAuthError',
                 'text': 'Can\'t authenticate on XMPP server with jid %s' % jid}
            raise web.HTTPError(502)
        except XMPPConnectionError as error:
            self.response['error'] = {'code': 'XMPPUpstreamConnectionError',
                                      'text': 'Can\'t connect to XMPP server %s' % error.server}
            raise web.HTTPError(502)
        except XMPPSendError:
            self.response['error'] = \
                {'code': 'XMPPUpstreamConnectionError', 'text': 'Message was not sent'}
            raise web.HTTPError(502)

        try:
            session = self.session_pool.session_for_id(session_id)
            self.response['session']['token'] = session_token
            self.response['session']['jid'] = session.jid
        except KeyError:
            self.response['error'] = \
                {'code': 'XMPPSessionError', 'text': 'There is no session with id %s' % session_id}
            raise web.HTTPError(404)

        self.write(self.response)


class SessionsHandler(XMPPClientHandler):
    def get(self):
        self.check_admin_access()
        sessions = []
        if self.should_expand:
            sessions = map(session_to_dict, self.session_pool.session_pool.values())
        else:
            sessions = self.session_pool.session_pool.keys()

        self.response['sessions'] = sessions
        self.write(self.response)


class SessionHandler(XMPPClientHandler):
    def get(self, session_id):
        session = self.get_session(session_id, accept_admin=True)
        self.response['session'] = session_to_dict(session)
        self.write(self.response)

    @gen.coroutine
    def delete(self, session_id):
        self.get_session(session_id, accept_admin=True)
        try:
            yield self.async_worker.submit(self.session_pool.close_session, session_id)
        except KeyError:
            self.response['error'] = \
                {'code': 'XMPPSessionError', 'text': 'There is no session with id %s' % session_id}
            raise web.HTTPError(404)

        self.write(self.response)

    def put(self, session_id):
        self.response['session'] = {'session_id': session_id}
        session = self.get_session(session_id)

        json_body = self.get_body()
        if 'session' not in json_body:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        session_body = json_body['session']

        if 'should_send_message_body' in session_body:
            session.should_send_message_body = session['should_send_message_body']


class SessionContactsHandler(XMPPClientHandler):
    def get(self, session_id):
        """
            Request parameters:
                offset - returns contacts which has been changed since offset or has
                messages with event_id greater than offset
        """
        session = self.get_session(session_id)
        offset = self.get_offset()

        self.response['contacts'] = session.contacts(event_offset=offset)
        self.write(self.response)

    @gen.coroutine
    def post(self, session_id):
        json_body = self.get_body()
        if 'contact' not in json_body:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        contact = json_body['contact']
        session = self.get_session(session_id)
        jid = contact.get('jid')
        contact_added = yield self.async_worker.submit(session.add_contact, jid,
                                                       contact.get('name'))

        timeout = 5.0
        while timeout and contact_added is None:
            ioloop.IOLoop.instance().add_timeout(timedelta(milliseconds=500),
                                                 (yield gen.Callback("wait")))
            yield gen.Wait("wait")
            timeout -= 0.5
            contact_added = session.contact_by_jid(jid)

        if contact_added is not None:
            self.response['contacts'] = [contact_added]
        else:
            self.raise_contact_error(jid)

        self.write(self.response)


class SessionMUCsHandler(XMPPClientHandler):
    def get(self, session_id):
        """
            Request parameters:
                offset - returns mucs which has been changed since offset or
                has messages with event_id greater than offset
        """
        session = self.get_session(session_id)
        offset = self.get_offset()

        self.response['mucs'] = session.mucs(event_offset=offset)
        self.write(self.response)

    @gen.coroutine
    def post(self, session_id):
        json_body = self.get_body()
        if 'muc' not in json_body:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        muc = json_body['muc']
        muc_node = muc.get('muc_jid_node')

        session = self.get_session(session_id)

        muc_added = yield self.async_worker.submit(session.create_muc, muc_node, muc.get('name'))

        timeout = 5.0
        while timeout and muc_added is None:
            ioloop.IOLoop.instance().add_timeout(timedelta(milliseconds=500),
                                                 (yield gen.Callback("wait")))
            yield gen.Wait("wait")
            timeout -= 0.5
            muc_added = session.muc_by_node(muc_node)

        if muc_added is not None:
            self.response['mucs'] = [muc_added]
        else:
            self.raise_contact_error(muc_node)

        self.write(self.response)


class SessionMessagesHandler(XMPPClientHandler):
    def get(self, session_id):
        """
            Request parameters:
                offset - returns messages with event_id greater that offset
        """
        session = self.get_session(session_id)
        offset = self.get_offset()

        self.response['messages'] = session.messages(event_offset=offset)
        self.write(self.response)


class SessionFeedHandler(XMPPClientHandler):
    @web.asynchronous
    @gen.coroutine
    def get(self, session_id):
        """
            Returns both - messages and contacts
            Request parameters:
                offset - returns objects which has been changed  or added since offset
        """
        offset = self.get_offset()
        session = self.get_session(session_id)

        contacts = session.contacts(event_offset=offset)
        mucs = session.mucs(event_offset=offset)
        messages = session.messages(event_offset=offset)

        if not len(contacts) + len(mucs) + len(messages) and self.should_wait:
            session.wait_for_notification(callback=(yield gen.Callback("notification")))
            yield gen.Wait("notification")
            contacts = session.contacts(event_offset=offset)
            mucs = session.mucs(event_offset=offset)
            messages = session.messages(event_offset=offset)

        self.response['contacts'] = contacts
        self.response['mucs'] = mucs
        self.response['messages'] = messages
        self.write(self.response)
        self.finish()


class SessionNotificationHandler(XMPPClientHandler):
    @web.asynchronous
    @gen.coroutine
    def get(self, session_id):
        self.response['session'] = {'session_id': session_id}
        session = self.get_session(session_id)
        session.wait_for_notification(callback=(yield gen.Callback("notification")))
        yield gen.Wait("notification")
        self.write(self.response)
        self.finish()


class ContactHandler(XMPPClientHandler):
    def get(self, session_id, contact_id):
        self.check_contact_id(contact_id)
        session = self.get_session(session_id)
        try:
            self.response['contact'] = session.contact(contact_id)
        except KeyError:
            self.raise_contact_error(contact_id)
        self.write(self.response)

    @gen.coroutine
    def put(self, session_id, contact_id):
        json_body = self.get_body()
        if 'contact' not in json_body:
            self.response['error'] =\
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_contact_id(contact_id)
        session = self.get_session(session_id)

        try:
            updated_contact = yield self.async_worker.submit(self.put_contact, session,
                                                             contact_id, json_body)
            self.response['contacts'] = [updated_contact]
        except KeyError:
            self.raise_contact_error(contact_id)

        self.write(self.response)

    @gen.coroutine
    def delete(self, session_id, contact_id):
        self.check_contact_id(contact_id)
        session = self.get_session(session_id)

        try:
            yield self.async_worker.submit(session.remove_contact, contact_id)
        except TypeError:
            self.raise_contact_error(contact_id)

        self.write(self.response)

    def put_contact(self, session, contact_id, json_body):
        contact = json_body['contact']
        if 'name' in contact:
            session.update_contact(contact_id, name=contact['name'])
        if 'read_offset' in contact:
            session.set_contact_read_offset(contact_id, contact['read_offset'])
        if 'history_offset' in contact:
            session.set_contact_history_offset(contact_id, contact['history_offset'])
        if 'authorization' in contact:
            session.set_contact_authorization(contact_id, contact['authorization'])

        return session.contact(contact_id)


class MucHandler(XMPPClientHandler):
    def get(self, session_id, muc_id):
        self.check_muc_id(muc_id)
        session = self.get_session(session_id)
        try:
            self.response['muc'] = session.muc(muc_id)
        except KeyError:
            self.raise_muc_error(muc_id)
        self.write(self.response)

    @gen.coroutine
    def put(self, session_id, muc_id):
        json_body = self.get_body()
        if 'muc' not in json_body:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_muc_id(muc_id)
        session = self.get_session(session_id)

        try:
            updated_muc = yield self.async_worker.submit(self.put_muc, session, muc_id, json_body)
            self.response['mucs'] = [updated_muc]
        except KeyError:
            self.raise_muc_error(muc_id)

        #waiting for invited users join MUC
        if 'muc' in json_body and json_body['muc'].get('invite') is not None:
            ioloop.IOLoop.instance().add_timeout(timedelta(milliseconds=2000),
                                                 (yield gen.Callback("wait")))
            yield gen.Wait("wait")
            self.response['mucs'] = [session.muc(muc_id)]

        self.write(self.response)

    @gen.coroutine
    def delete(self, session_id, muc_id):
        self.check_muc_id(muc_id)
        session = self.get_session(session_id)

        try:
            yield self.async_worker.submit(session.remove_muc, muc_id)
        except TypeError:
            self.raise_muc_error(muc_id)

        self.write(self.response)

    def put_muc(self, session, muc_id, json_body):
        muc = json_body['muc']
        if 'name' in muc:
            session.update_muc(muc_id, name=muc['name'])
        if 'read_offset' in muc:
            session.set_muc_read_offset(muc_id, muc['read_offset'])
        if 'history_offset' in muc:
            session.set_muc_history_offset(muc_id, muc['history_offset'])
        if 'invite' in muc:
            session.invite_to_muc(self, muc_id, muc['invite'])

        return session.muc(muc_id)


class ContactMessagesHandler(XMPPClientHandler):
    def get(self, session_id, contact_id):
        """
            Request parameters:
                offset - returns messages with event_id greater that offset
        """
        self.check_contact_id(contact_id)
        session = self.get_session(session_id)
        offset = self.get_offset()

        try:
            self.response['messages'] = session.messages(contact_ids=[contact_id],
                                                         event_offset=offset)
        except TypeError:
            self.raise_contact_error(contact_id)

        self.write(self.response)

    @gen.coroutine
    def post(self, session_id, contact_id):
        json_body = self.get_body()
        try:
            message = json_body['messages']['text']
        except KeyError:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_contact_id(contact_id)
        session = self.get_session(session_id)

        try:
            self.response['messages'] = yield self.async_worker.submit(session.send,
                                                                       contact_id, message)
        except XMPPSendError:
            self.raise_message_sending_error()
        except TypeError:
            self.raise_contact_error(contact_id)

        self.write(self.response)


class MucMessagesHandler(XMPPClientHandler):
    def get(self, session_id, muc_id):
        """
            Request parameters:
                offset - returns messages with event_id greater that offset
        """
        self.check_muc_id(muc_id)
        session = self.get_session(session_id)
        offset = self.get_offset()

        try:
            self.response['messages'] = session.messages(contact_ids=[muc_id], event_offset=offset)
        except TypeError:
            self.raise_muc_error(muc_id)

        self.write(self.response)

    @gen.coroutine
    def post(self, session_id, muc_id):
        json_body = self.get_body()
        try:
            message = json_body['messages']['text']
        except KeyError:
            self.response['error'] = \
                {'code': 'XMPPServiceParametersError', 'text': 'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_muc_id(muc_id)
        session = self.get_session(session_id)

        try:
            self.response['messages'] = yield self.async_worker.submit(session.send,
                                                                       muc_id, message)
        except XMPPSendError:
            self.raise_message_sending_error()
        except TypeError:
            self.raise_muc_error(muc_id)

        self.write(self.response)


class ServerStatusHandler(XMPPClientHandler):
    def get(self):
        response = {}
        try:
            import psutil

            def sizeof_fmt(num):
                for x in ['B', 'kB', 'MB', 'GB']:
                    if num < 1024.0:
                        return {'value': num, 'units': x}
                    num /= 1024.0
                return {'value': num, 'units': 'TB'}
            process = psutil.Process(os.getpid())
            response['memory'] = sizeof_fmt(process.get_memory_info()[0])
            response['threads'] = process.get_num_threads()
        except ImportError:
            pass

        response['im_sessions'] = len(self.session_pool.session_pool.keys())
        response['im_clients'] = len(self.session_pool.im_client_pool.keys())
        response['xmpp_clients'] = len(self.session_pool.xmpp_client_pool.keys())
        self.write(response)
