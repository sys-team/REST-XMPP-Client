# -*- coding: utf-8 -*-

__author__ = 'kovtash'

import os
import logging
from bottle import Bottle, template, request, abort
from xmpp_session_pool import  XMPPAuthError, XMPPConnectionError, XMPPSendError, XMPPRosterError, XMPPSendError
from xmpp_session_pool import XMPPPlugin

xmpp_plugin = XMPPPlugin(debug=False)

app = Bottle(__name__)
app.install(xmpp_plugin)

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
        response['error'] = {'code':'XMPPAuthError','text':template('No authorization information provided')}
        abort(502, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    if not auth_header[7:] == session.token:
        response['error'] = {'code':'XMPPAuthError','text':template('Wrong authorization data')}
        abort(502, response)

    return session


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
        response['error'] = {'code':'XMPPAuthError','text':template('Service for {{jid}} can\'t authenticate on xmpp server',jid=jid)}
        abort(502, response)
    except XMPPConnectionError as error:
        response['error'] = {'code':'XMPPConnectionError','text':template('Service can\'t connect to xmpp server {{server}}',server=error.server)}
        abort(502, response)
    except XMPPSendError:
        response['error'] = {'code':'XMPPConnectionError','text':'Message was not sent'}
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
    response = {'session':{'session_id':session_id}}

    check_session_id(session_id,response)

    try:
        xmpp_pool.close_session(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    return

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

    try:
        response['messages'] = session.messages(timestamp=offset)
        session.reset_new_messages_counter()
    except TypeError:
        raise_contact_error(contact_id,response)

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

    return

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

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    logging.basicConfig(level=logging.DEBUG)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, server='cherrypy') #reloader=True
    xmpp_plugin.__del__()
