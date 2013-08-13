__author__ = 'kovtash'

from tornado import web, gen, ioloop
from xmpp_session_pool import XMPPAuthError, XMPPConnectionError, XMPPSendError
from datetime import timedelta
import json
import psutil
import os
import time


class MainHandler(web.RequestHandler):
    def initialize(self, async_worker):
        self.async_worker = async_worker

    @gen.coroutine
    def get(self):
        result = yield self.async_worker.submit(self.work, 'Done')
        self.write(result)

    def work(self,message):
        time.sleep(10)
        return message


class XMPPClientHandler(web.RequestHandler):
    def initialize(self, session_pool, async_worker):
        self.session_pool = session_pool
        self.async_worker = async_worker
        self.response = {}

    def write_error(self, status_code, **kwargs):
        self.write(self.response)

    def raise_value_error(self, parameter_name):
        self.response['error'] = {'code':'XMPPServiceParametersError','text':'Parameter %s has wrong value'%parameter_name}
        raise web.HTTPError(400)

    def raise_message_sending_error(self):
        self.response['error'] = {'code':'XMPPSendError','text':'Message sending failed'}
        raise web.HTTPError(404)

    def raise_contact_error(self, contact_id):
        self.response['error'] = {'code':'XMPPContactError','text':'There is no contact with id %s'%contact_id}
        raise web.HTTPError(404)

    def check_contact_id(self,contact_id):
        if contact_id is None:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing contact_id parameter'}
            raise web.HTTPError(400)

    def get_header(self, header_name):
        if  header_name in self.request.headers:
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

    def get_should_wait(self):
        should_wait_param = self.get_argument('wait', None)
        should_wait = False
        if should_wait_param is not None:
            try:
                should_wait = bool(should_wait_param)
            except ValueError:
                self.raise_value_error('wait')

        return should_wait

    def get_session(self, session_id):
        if session_id is None:
            self.response['error'] = {'code':'XMPPServiceParametersError', 'text':'Missing session_id parameter'}
            raise web.HTTPError(400)

        auth_header = self.get_header('Authorization')

        if auth_header is None:
            self.response['error'] = {'code':'XMPPAuthError','text':'No authorization information provided'}
            raise web.HTTPError(502)

        try:
            session = self.session_pool.session_for_id(session_id)
        except KeyError:
            self.response['error'] = {'code':'XMPPSessionError','text':'There is no session with id %s'%session_id}
            raise web.HTTPError(404)

        if not auth_header[7:] == session.token:
            self.response['error'] = {'code':'XMPPAuthError','text':'Wrong authorization data'}
            raise web.HTTPError(401)

        return session

    def get_body(self):
        if self.request.body is None:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing request body'}
            raise web.HTTPError(400)
        else:
            try:
                body = json.loads(self.request.body)
            except ValueError:
                self.response['error']={'code':'XMPPServiceParametersError','text':'Not a valid JSON format'}
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

        if jid is None or password is None or server is None:
            self.response['error'] = {'code':'XMPPServiceParametersError', 'text':'Missing required parameters'}
            raise web.HTTPError(400)

        try:
            session_id = yield self.async_worker.submit(self.session_pool.start_session, jid=jid, password=password, server=server, push_token=push_token, im_client_id=client_id)
            self.response['session'] = {'session_id':session_id}
        except XMPPAuthError:
            self.response['error'] = {'code':'XMPPUpstreamAuthError', 'text':'Can\'t authenticate on XMPP server with jid %s'%jid}
            raise web.HTTPError(502)
        except XMPPConnectionError as error:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError', 'text':'Can\'t connect to XMPP server %s'%error.server}
            raise web.HTTPError(502)
        except XMPPSendError:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError', 'text':'Message was not sent'}
            raise web.HTTPError(502)

        try:
            session = self.session_pool.session_for_id(session_id)
            self.response['session']['token'] = session.token
            self.response['session']['jid'] = session.jid
        except KeyError:
            self.response['error'] = {'code':'XMPPSessionError', 'text':'There is no session with id %s'%session_id}
            raise web.HTTPError(404)

        self.write(self.response)


class SessionHandler(XMPPClientHandler):
    def get(self, session_id):
        self.response['session'] = {'session_id':session_id}
        session = self.get_session(session_id)
        self.response['session']['jid'] = session.jid
        self.response['session']['should_send_message_body'] = session.should_send_message_body

        self.write(self.response)

    @gen.coroutine
    def delete(self, session_id):
        self.get_session(session_id)
        try:
            result = yield self.async_worker.submit(self.session_pool.close_session, session_id)
        except KeyError:
            self.response['error'] = {'code':'XMPPSessionError', 'text':'There is no session with id %s'%session_id}
            raise web.HTTPError(404)

        self.write(self.response)

    def put(self, session_id):
        self.response['session'] = {'session_id':session_id}
        session = self.get_session(session_id)

        json_body = self.get_body()
        if 'session' not in json_body:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
            raise web.HTTPError(400)

        session_body = json_body['session']

        if 'should_send_message_body' in session_body:
            session.should_send_message_body = session['should_send_message_body']


class SessionContactsHandler(XMPPClientHandler):
    def get(self, session_id):
        """
            Request parameters:
                offset - returns contacts which has been changed since offset or has messages with event_id greater than offset
        """
        session = self.get_session(session_id)
        offset = self.get_offset()

        self.response['contacts'] = session.contacts(event_offset=offset)
        self.write(self.response)

    @gen.coroutine
    def post(self, session_id):
        json_body = self.get_body()
        if 'contact' not in json_body:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
            raise web.HTTPError(400)

        contact = json_body['contact']
        session = self.get_session(session_id)
        contact_added = yield self.async_worker.submit(self.add_contact, session, contact.get('jid'), contact.get('name'))
        if contact_added is not None:
            self.response['contacts'] = [contact_added]
        else:
            self.raise_contact_error(contact.get('jid'))

        self.write(self.response)

    def add_contact(self, session, jid, name):
        session.add_contact(jid, name)
        timeout = 5.0
        contact_added = session.contact_by_jid(jid)
        while timeout and contact_added is None:
            time.sleep(0.5)
            timeout -= 0.5
            contact_added = session.contact_by_jid(jid)
        return contact_added


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
        should_wait = self.get_should_wait()
        session = self.get_session(session_id)

        self.response['contacts'] = session.contacts(event_offset=offset)
        self.response['messages'] = session.messages(event_offset=offset)

        if (not (len(self.response['contacts'])+len(self.response['messages'])) and should_wait):
            session.wait_for_notification(callback = (yield gen.Callback("notification")))
            yield gen.Wait("notification")
            session = self.get_session(session_id)
            self.response['contacts'] = session.contacts(event_offset=offset)
            self.response['messages'] = session.messages(event_offset=offset)
            #timeout added for requests synchronization
            #all post and put requests should return result earlier than polling request
            ioloop.IOLoop.instance().add_timeout(timedelta(milliseconds=500), (yield gen.Callback("wait")))
            yield gen.Wait("wait")

        self.write(self.response)
        self.finish()


class SessionNotificationHandler(XMPPClientHandler):
    @web.asynchronous
    @gen.coroutine
    def get(self, session_id):
        self.response['session'] = {'session_id':session_id}
        session = self.get_session(session_id)
        session.wait_for_notification(callback = (yield gen.Callback("notification")))
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
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_contact_id(contact_id)
        session = self.get_session(session_id)

        try:
            updated_contact = yield self.async_worker.submit(self.put_contact, session, contact_id, json_body)
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
        if 'authorization' in contact:
            session.set_contact_authorization(contact_id, contact['authorization'])

        return session.contact(contact_id)


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
            self.response['messages'] = session.messages(contact_ids=[contact_id], event_offset=offset)
        except TypeError:
            self.raise_contact_error(contact_id)

        self.write(self.response)

    @gen.coroutine
    def post(self, session_id, contact_id):
        json_body = self.get_body()
        try:
            message = json_body['messages']['text']
        except KeyError:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
            raise web.HTTPError(400)

        self.check_contact_id(contact_id)
        session = self.get_session(session_id)

        try:
            self.response['messages'] = yield self.async_worker.submit(session.send, contact_id, message)
        except XMPPSendError:
            self.raise_message_sending_error()
        except TypeError:
            self.raise_contact_error(contact_id)

        self.write(self.response)


class ServerStatusHandler(XMPPClientHandler):
    def get(self):
        def sizeof_fmt(num):
            for x in ['B','kB','MB','GB']:
                if num < 1024.0:
                    return {'value':num, 'units':x}
                num /= 1024.0
            return {'value':num, 'units':'TB'}

        response = {}
        process = psutil.Process(os.getpid())

        response['memory'] = sizeof_fmt(process.get_memory_info()[0])
        response['threads'] = process.get_num_threads()
        response['im_sessions'] = len(self.session_pool.session_pool.keys())
        response['im_clients'] = len(self.session_pool.im_client_pool.keys())
        response['xmpp_clients'] = len(self.session_pool.xmpp_client_pool.keys())
        self.write(response)