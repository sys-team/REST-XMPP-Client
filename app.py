# -*- coding: utf-8 -*-

__author__ = 'kovtash'

import os
import logging
from bottle import Bottle, template, request, abort
from xmpp_session_pool import  XMPPAuthError, XMPPConnectionError, XMPPSendError, XMPPRosterError, XMPPSendError
from xmpp_session_pool import XMPPPlugin

xmpp_plugin = XMPPPlugin()

app = Bottle(__name__)
app.install(xmpp_plugin)

def raise_message_sending_error(response):
    response['error'] = {'code':'XMPPSendError','text':'Message sending failed'}
    abort(404, response)

def raise_contact_error(contact_id,response):
    response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
    abort(404, response)

def check_session_id(session_id,response):
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing session_id parameter'}
        abort(400, response)

def check_contact_id(contact_id,response):
    if contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing contact_id parameter'}
        abort(400, response)

def get_session(xmpp_pool,session_id,response):
    try:
        session = xmpp_pool.session_for_id(session_id)
        return session
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)


@app.route('/')
def start_session(xmpp_pool):
    jid = request.query.get('jid')
    password = request.query.get('password')
    server = request.query.get('server')
    response = {'session':{}}
    
    if jid is None or password is None or server is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)
    
    try:
        session_id = xmpp_pool.start_session(jid,password,server)
        response['session']['session_id'] = session_id
        session = get_session(xmpp_pool,session_id,response)
        response['session']['token'] = session.token
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
    session = get_session(xmpp_pool,session_id,response)
        
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
    
@app.route('/sessions/<session_id>/contacts')
def session_contacts(xmpp_pool,session_id=None):
    response = {}

    jid = request.query.get('jid',None)

    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,response)

    if jid is None:
        response = {'contacts':{}}
        response['contacts'] = session.contacts()
    else:
        session.add_contact(jid)
        response['contact'] = session.contactByJID(jid)
        
    return response
    
@app.route('/sessions/<session_id>/contacts/<contact_id>')
def session_contact(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,response)
        
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
    session = get_session(xmpp_pool,session_id,response)

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
    session = get_session(xmpp_pool,session_id,response)

    try:
        session.remove_contact(contact_id)
    except TypeError:
        raise_contact_error(contact_id,response)

    return

@app.route('/sessions/<session_id>/contacts/<contact_id>/chat')
def contact_messages(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    message = request.query.get('message',None)

    check_session_id(session_id,response)
    check_contact_id(contact_id,response)
    session = get_session(xmpp_pool,session_id,response)
        
    if message is None:
        try:
            response['messages'] = session.messages(contact_id)
        except TypeError:
            raise_contact_error(contact_id,response)
    else:
        response['message'] = {'text':message}
        try:
            response['message']['id'] = session.send(contact_id,message)
        except XMPPSendError:
            raise_message_sending_error(response)
        except TypeError:
            raise_contact_error(contact_id,response)
        
    return response

@app.route('/sessions/<session_id>/chats')
def session_messages(xmpp_pool,session_id=None):
    message = request.query.get('message',None)
    contact_id = request.query.get('contact_id',None)
    jid = request.query.get('jid',None)
    response = {}

    check_session_id(session_id,response)
    session = get_session(xmpp_pool,session_id,response)

    if  message is None and contact_id is None and jid is None:
        response['messages'] = session.all_messages()
    else:
        if message is None:
            response['error'] = {'code':'XMPPServiceParametersError','text':'Missing message parameter'}
            abort(400, response)

        response['message'] = {'contact_id':contact_id,'text':message}
        try:
            if contact_id is not None:
                response['message']['contact_id'] = contact_id
                response['message']['id'] = session.send(contact_id,message)
            elif jid is not None:
                response['message']['jid'] = jid
                response['message']['id'] = session.sendByJID(jid,message)
            else:
                response['error'] = {'code':'XMPPServiceParametersError','text':'Missing contact_id or jid parameter'}
                abort(400, response)
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
