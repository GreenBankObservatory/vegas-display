import tornado.web
import tornado.ioloop

import os
import sys

from zmq_web_socket import ZMQWebSocket
from server_config import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title='Vegas Data Display')

def listen_for_display_clients(port_number):
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }

    application = tornado.web.Application([
         # when someone goes to the main page url:port
         # invoke MainHandler, which loads html that loads Display.js,
         # which opens url:port/websocket that invokes ZMQWebSocket
        (r"/", MainHandler),
        (r"/websocket", ZMQWebSocket)
    ], **settings)

    application.listen(port_number, '0.0.0.0')
    try:
        print 'start ioloop listenting to port', port_number
        tornado.ioloop.IOLoop.instance().start()
        print 'left ioloop'
    except KeyboardInterrupt:
        sys.exit()

if __name__ == "__main__":

    # Handle requests from clients to pass data from the stream

    listen_for_display_clients(PORT_NUMBER)
