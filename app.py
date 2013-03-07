# -*- coding: utf-8 -*-

__author__ = 'kovtash'

import os
import json
import logging
from bottle import Bottle, template, request, abort
from xmpp_session_pool import  XMPPAuthError, XMPPConnectionError, XMPPSendError, XMPPRosterError, XMPPSendError
from xmpp_session_pool import XMPPPlugin

xmpp_plugin = XMPPPlugin()

app = Bottle(__name__)
app.install(xmpp_plugin)

@app.route('/')
def start_session(xmpp_pool):
    jid = request.query.get('jid')
    password = request.query.get('password')
    server = request.query.get('server')
    response = {'session':{}}
    
    if jid is None or password is None or server is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))
    
    try:
        session_id = xmpp_pool.start_session(jid,password,server)
        response['session']['session_id'] = session_id
    except XMPPAuthError:
        response['error'] = {'code':'XMPPAuthError','text':template('Service for {{jid}} can\'t authenticate on xmpp server',jid=jid)}
        abort(502, json.dumps(response))
    except XMPPConnectionError as error:
        response['error'] = {'code':'XMPPConnectionError','text':template('Service can\'t connect to xmpp server {{server}}',server=error.server)}
        abort(502, json.dumps(response))
    except XMPPSendError:
        response['error'] = {'code':'XMPPConnectionError','text':'Message was not sent'}
        abort(502, json.dumps(response))
    
    return json.dumps(response)
    
@app.route('/sessions/<session_id>')
def session(xmpp_pool,session_id=None):
    response = {'session':{'session_id':session_id}}
    
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))
        
    return json.dumps(response)

@app.route('/sessions/<session_id>/remove')
def session(xmpp_pool,session_id=None):
    response = {'session':{'session_id':session_id}}

    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    try:
        xmpp_pool.close_session(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))

    return json.dumps(response)
    
@app.route('/sessions/<session_id>/contacts')
def session_contacts(xmpp_pool,session_id=None):
    response = {}

    jid = request.query.get('jid',None)
    
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))

    if jid is None:
        response = {'contacts':{}}
        response['contacts'] = session.contacts()
    else:
        session.add_contact(jid)
        response['contact'] = session.contact(jid)
        
    return json.dumps(response)
    
@app.route('/sessions/<session_id>/contacts/<jid>')
def session_contact(xmpp_pool,session_id=None,jid=None):
    response = {}
    
    if session_id is None or jid is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))
        
    try:
        response['contact'] = session.contact(jid)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{jid}}',jid=jid)}
        abort(404, json.dumps(response))
        
    return json.dumps(response)

@app.route('/sessions/<session_id>/contacts/<jid>/authorize')
def session_contact_authorize(xmpp_pool,session_id=None,jid=None):
    response = {}

    if session_id is None or jid is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))


    if jid in session.contacts():
        session.authorize_contact(jid)
        response['contact'] = session.contact(jid)
    else:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{jid}}',jid=jid)}
        abort(404, json.dumps(response))

    return json.dumps(response)

@app.route('/sessions/<session_id>/contacts/<jid>/remove')
def session_contact_remove(xmpp_pool,session_id=None,jid=None):
    response = {}

    if session_id is None or jid is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))

    session.remove_contact(jid)

    return json.dumps(response)

@app.route('/sessions/<session_id>/contacts/<jid>/messages')
def contact_messages(xmpp_pool,session_id=None,jid=None):
    message = request.query.get('message',None)
    response = {}
    
    if session_id is None or jid is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))    
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))
        
    if message is None:
        response['messages'] = session.messages(jid)
        return json.dumps(response)
            
    try:
        session.send(jid,message)
    except XMPPSendError:
        response['error'] = {'code':'XMPPSendError','text':template('Message sending failed')}
        abort(404, json.dumps(response))
        
    response['message'] = message
        
    return json.dumps(response)

@app.route('/sessions/<session_id>/messages')
def session_messages(xmpp_pool,session_id=None):
    message = request.query.get('message',None)
    jid = request.query.get('jid',None)
    response = {}

    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, json.dumps(response))

    if  message is None and jid is None:
        response['messages'] = session.all_messages()
        return json.dumps(response)

    if message is None or jid is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, json.dumps(response))

    response['message'] = {'jid':jid,'text':message}

    try:
        response['message']['id'] = session.send(jid,message)
    except XMPPSendError:
        response['error'] = {'code':'XMPPSendError','text':template('Message sending failed')}
        abort(404, json.dumps(response))

    return json.dumps(response)

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    logging.basicConfig(level=logging.DEBUG)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, server='cherrypy') #reloader=True
    xmpp_plugin.__del__()
