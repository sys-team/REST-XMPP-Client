# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import os
import logging
from rest2xmpp import app

if __name__ == '__main__':
    # Bind to PORT if defined, otherwise default to 5000.
    logging.basicConfig(level=logging.DEBUG)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, server='cherrypy') #reloader=True
    app.close()
