# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import resource
import json
from bottle import Bottle, template, request, abort, response
from xmpp_plugin import XMPPPlugin, XMPPAuthError, XMPPConnectionError, XMPPSendError

app = Bottle(catchall=True)
app.install(XMPPPlugin(debug=False))

def raise_message_sending_error(response):
    response['error'] = {'code':'XMPPSendError','text':'Message sending failed'}
    abort(404, response)

def raise_contact_error(contact_id,response):
    response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
    abort(404, response)

def raise_value_error(parameter_name,response):
    response['error'] = {'code':'XMPPServiceParametersError','text':template('Parameter {{parameter}} has wrong value',parameter=parameter_name)}
    abort(400, response)

def check_session_id(session_id,response):
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing session_id parameter'}
        abort(400, response)

def check_contact_id(contact_id,response):
    if contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing contact_id parameter'}
        abort(400, response)

def get_offset(request,response):
    offset = request.query.get('offset',None)

    if offset is not None:
        try:
            offset = float(offset)
        except ValueError:
            raise_value_error('offset',response)

    return offset

def get_session(xmpp_pool,session_id,request,response):
    auth_header = request.get_header('Authorization')

    if auth_header is None:
        response['error'] = {'code':'XMPPAuthError','text':'No authorization information provided'}
        abort(502, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    if not auth_header[7:] == session.token:
        response['error'] = {'code':'XMPPAuthError','text':'Wrong authorization data'}
        abort(401, response)

    return session

def error_body(error):
    response.content_type = 'application/json'
    return json.dumps(error.output)

@app.error(400)
def error400(error):
    return error_body(error)

@app.error(401)
def error400(error):
    return error_body(error)

@app.error(404)
def error404(error):
    return error_body(error)

@app.error(500)
def error500(error):
    return error_body(error)

@app.error(502)
def error502(error):
    return error_body(error)

@app.post('/start-session')
def start_session(xmpp_pool):
    jid = request.forms.get('jid')
    password = request.forms.get('password')
    server = request.forms.get('server')
    push_token = request.forms.get('push_token')
    response = {'session':{}}

    if jid is None or password is None or server is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        session_id = xmpp_pool.start_session(jid,password,server,push_token)
        response['session']['session_id'] = session_id
        session = xmpp_pool.session_for_id(session_id)
        response['session']['token'] = session.token
        response['session']['jid'] = session.jid.getStripped()
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)
    except XMPPAuthError:
        response['error'] = {'code':'XMPPUpstreamAuthError','text':template('Can\'t authenticate on XMPP server with jid {{jid}}',jid=jid)}
        abort(502, response)
    except XMPPConnectionError as error:
        response['error'] = {'code':'XMPPUpstreamConnectionError','text':template('Can\'t connect to XMPP server {{server}}',server=error.server)}
        abort(502, response)
    except XMPPSendError:
        response['error'] = {'code':'XMPPUpstreamConnectionError','text':'Message was not sent'}
        abort(502, response)

    return response

@app.route('/sessions/<session_id>')
def session(xmpp_pool,session_id=None):
    response = {'session':{'session_id':session_id}}

    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,request,response)
    response['session']['jid'] = session.jid.getStripped()

    return response

@app.delete('/sessions/<session_id>')
@app.route('/sessions/<session_id>/delete')
def session(xmpp_pool,session_id=None):
    response = {}

    check_session_id(session_id,response)

    try:
        xmpp_pool.close_session(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    return response

@app.route('/sessions/<session_id>/notification')
def session(xmpp_pool,session_id=None):
    response = {'session':{'session_id':session_id}}

    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,request,response)
    if not session.poll_changes():
        abort(404, response)
    return response

@app.route('/sessions/<session_id>/messages')
def session(xmpp_pool,session_id=None):
    """
        Request parameters:
            offset - returns messages with timestamp greater that offset
    """
    response = {}

    offset = get_offset(request,response)
    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    response['messages'] = session.messages(timestamp=offset)
    session.reset_new_messages_counter()

    return response

@app.route('/sessions/<session_id>/contacts')
def session_contacts(xmpp_pool,session_id=None):
    """
        Request parameters:
            offset - returns contacts which has been changed since offset or has messages with timestamp greater than offset
    """
    response = {}

    offset = get_offset(request,response)
    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    response['contacts'] = session.contacts(timestamp=offset)

    return response

@app.route('/sessions/<session_id>/feed')
def session_feed(xmpp_pool,session_id=None):
    """
        Returns both - messages and contacts
        Request parameters:
            offset - returns objects which has been changed  or added since offset
    """
    response = {}
    offset = get_offset(request,response)
    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    response['contacts'] = session.contacts(timestamp=offset)
    response['messages'] = session.messages(timestamp=offset)
    session.reset_new_messages_counter()

    return response

@app.route('/sessions/<session_id>/contacts/<contact_id>')
def session_contact(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    try:
        response['contact'] = session.contact(contact_id)
    except KeyError:
        raise_contact_error(contact_id,response)

    return response

@app.route('/sessions/<session_id>/contacts/<contact_id>/authorize')
def session_contact_authorize(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    if contact_id in session.contacts():
        session.authorize_contact(contact_id)
        response['contact'] = session.contact(contact_id)
    else:
        raise_contact_error(contact_id,response)

    return response

@app.delete('/sessions/<session_id>/contacts/<contact_id>')
@app.route('/sessions/<session_id>/contacts/<contact_id>/delete')
def session_contact_remove(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    try:
        session.remove_contact(contact_id)
    except TypeError:
        raise_contact_error(contact_id,response)

    return response

@app.get('/sessions/<session_id>/contacts/<contact_id>/messages')
def contact_messages(xmpp_pool,session_id=None,contact_id=None):
    """
        Request parameters:
            offset - returns messages with timestamp greater that offset
    """
    response = {}

    offset = get_offset(request,response)
    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    try:
        response['messages'] = session.messages(contact_ids=[contact_id],timestamp=offset)
        session.reset_new_messages_counter()
    except TypeError:
        raise_contact_error(contact_id,response)

    return response

@app.post('/sessions/<session_id>/contacts/<contact_id>/messages')
def contact_messages(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    if request.json is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
        abort(400, response)

    try:
        message = request.json['messages']['text']
    except KeyError:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing or wrong request body'}
        abort(400, response)

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,request,response)

    if message is None:
        try:
            response['messages'] = session.messages(contact_ids=[contact_id])
        except TypeError:
            raise_contact_error(contact_id,response)
    else:
        try:
            response['messages'] = session.send(contact_id,message)
        except XMPPSendError:
            raise_message_sending_error(response)
        except TypeError:
            raise_contact_error(contact_id,response)

    return response

@app.route('/server-status')
def server_status(xmpp_pool):
    response = {}
    response['memory'] = {}

    memory_value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    if 1024 < memory_value < 1024*1024:
        response['memory']['value'] = memory_value / float(1024)
        response['memory']['units'] = 'kB'
    elif 1024*1024 < memory_value < 1024*1024*1024:
        response['memory']['value'] = memory_value / float(1024*1024)
        response['memory']['units'] = 'MB'
    elif 1024*1024*1024 < memory_value < 1024*1024*1024*1024:
        response['memory']['value'] = memory_value / float(1024*1024*1024)
        response['memory']['units'] = 'GB'
    else:
        response['memory']['value'] = memory_value
        response['memory']['units'] = 'B'

    response['sessions'] = len(xmpp_pool.session_pool.keys())
    return response
