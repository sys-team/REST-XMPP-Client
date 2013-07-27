__author__ = 'kovtash'

import tornado.web
from xmpp_session_pool import XMPPAuthError, XMPPConnectionError, XMPPSendError

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

class XMPPClientHandler(tornado.web.RequestHandler):
    def initialize(self, session_pool):
        self.session_pool = session_pool
        self.response = {}

    def write_error(self, status_code, **kwargs):
        self.write(self.response)

class StartSession(XMPPClientHandler):
    def post(self):
        jid = self.get_argument('jid',default=None)
        password = self.get_argument('password',default=None)
        server = self.get_argument('server',default=None)
        push_token = self.get_argument('push_token',default=None)
        client_id = self.get_argument('client_id',default=None)

        if jid is None or password is None or server is None:
            self.response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
            raise tornado.web.HTTPError(400)

        self.response['session'] = {}

        try:
            session_id = self.session_pool.start_session(jid=jid,password=password,server=server,push_token=push_token,im_client_id=client_id)
            self.response['session']['session_id'] = session_id
            session = self.session_pool.session_for_id(session_id)
            self.response['session']['token'] = session.token
            self.response['session']['jid'] = session.jid
        except KeyError:
            self.response['error'] = {'code':'XMPPSessionError','text':'There is no session with id %s'%session_id}
            raise tornado.web.HTTPError(404)
        except XMPPAuthError:
            self.response['error'] = {'code':'XMPPUpstreamAuthError','text':'Can\'t authenticate on XMPP server with jid %s'%jid}
            raise tornado.web.HTTPError(502)
        except XMPPConnectionError as error:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError','text':'Can\'t connect to XMPP server %s'%error.server}
            raise tornado.web.HTTPError(502)
        except XMPPSendError:
            self.response['error'] = {'code':'XMPPUpstreamConnectionError','text':'Message was not sent'}
            raise tornado.web.HTTPError(502)

        self.write(self.response)
