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
    
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)
        
    return response

@app.route('/sessions/<session_id>/remove')
def session(xmpp_pool,session_id=None):
    response = {'session':{'session_id':session_id}}

    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        xmpp_pool.close_session(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    return response
    
@app.route('/sessions/<session_id>/contacts')
def session_contacts(xmpp_pool,session_id=None):
    response = {}

    jid = request.query.get('jid',None)
    
    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

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
    
    if session_id is None or contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)
        
    try:
        response['contact'] = session.contact(contact_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
        abort(404, response)
        
    return response

@app.route('/sessions/<session_id>/contacts/<contact_id>/authorize')
def session_contact_authorize(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    if session_id is None or contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)


    if contact_id in session.contacts():
        session.authorize_contact(contact_id)
        response['contact'] = session.contact(contact_id)
    else:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
        abort(404, response)

    return response

@app.route('/sessions/<session_id>/contacts/<contact_id>/remove')
def session_contact_remove(xmpp_pool,session_id=None,contact_id=None):
    response = {}

    if session_id is None or contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    try:
        session.remove_contact(contact_id)
    except TypeError:
        response['error'] = {'code':'XMPPContactError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
        abort(404, response)

    return response

@app.route('/sessions/<session_id>/contacts/<contact_id>/messages')
def contact_messages(xmpp_pool,session_id=None,contact_id=None):
    message = request.query.get('message',None)
    response = {}
    
    if session_id is None or contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)    
    
    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)
        
    if message is None:
        try:
            response['messages'] = session.messages(contact_id)
        except TypeError:
            response['error'] = {'code':'XMPPContactError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
            abort(404, response)
    else:
        try:
            session.send(contact_id,message)
        except XMPPSendError:
            response['error'] = {'code':'XMPPSendError','text':template('Message sending failed')}
            abort(404, response)

        except TypeError:
            response['error'] = {'code':'XMPPContactError','text':template('There is no contact with id {{contact_id}}',contact_id=contact_id)}
            abort(404, response)

        
    response['message'] = message
        
    return response

@app.route('/sessions/<session_id>/messages')
def session_messages(xmpp_pool,session_id=None):
    message = request.query.get('message',None)
    contact_id = request.query.get('contact_id',None)
    response = {}

    if session_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    try:
        session = xmpp_pool.session_for_id(session_id)
    except KeyError:
        response['error'] = {'code':'XMPPSessionError','text':template('There is no session with id {{session_id}}',session_id=session_id)}
        abort(404, response)

    if  message is None and contact_id is None:
        response['messages'] = session.all_messages()
        return response

    if message is None or contact_id is None:
        response['error'] = {'code':'XMPPServiceParametersError','text':'Missing required parameters'}
        abort(400, response)

    response['message'] = {'jid':contact_id,'text':message}

    try:
        response['message']['id'] = session.send(contact_id,message)
    except XMPPSendError:
        response['error'] = {'code':'XMPPSendError','text':template('Message sending failed')}
        abort(404, response)

    return response

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    logging.basicConfig(level=logging.DEBUG)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, server='cherrypy') #reloader=True
    xmpp_plugin.__del__()
