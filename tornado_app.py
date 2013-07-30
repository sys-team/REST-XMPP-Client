__author__ = 'kovtash'

from tornado import web
from tornado import gen
from xmpp_session_pool import XMPPAuthError, XMPPConnectionError, XMPPSendError
import time

class MainHandler(web.RequestHandler):
    def initialize(self, async_worker):
        self.async_worker = async_worker

    @gen.coroutine
    def get(self):
        result = yield self.async_worker.submit(self.work,'Done')
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

class StartSession(XMPPClientHandler):
    @gen.coroutine
    def post(self):
        jid = self.get_argument('jid',default=None)
        password = self.get_argument('password',default=None)
        server = self.get_argument('server',default=None)
        push_token = self.get_argument('push_token',default=None)
        client_id = self.get_argument('client_id',default=None)

        if jid is None or password is None or server is None:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
            raise web.HTTPError(400)

        try:
            session_id = yield self.async_worker.submit(self.session_pool.start_session,jid=jid,password=password,server=server,push_token=push_token,im_client_id=client_id)
            self.response['session'] = {'session_id':session_id}
        except XMPPAuthError:
            self.response['error'] = {'code':'XMPPUpstreamAuthError','text':'Can\'t authenticate on XMPP server with jid %s'%jid}
            raise web.HTTPError(502)
        except XMPPConnectionError as error:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError','text':'Can\'t connect to XMPP server %s'%error.server}
            raise web.HTTPError(502)
        except XMPPSendError:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError','text':'Message was not sent'}
            raise web.HTTPError(502)

        try:
            session = self.session_pool.session_for_id(session_id)
            self.response['session']['token'] = session.token
            self.response['session']['jid'] = session.jid
        except KeyError:
            self.response['error'] = {'code':'XMPPSessionError','text':'There is no session with id %s'%session_id}
            raise web.HTTPError(404)

        self.write(self.response)
