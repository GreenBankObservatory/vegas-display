import tornado.web
import tornado.ioloop

import os
import sys
import logging
import argparse

from zmq_web_socket import ZMQWebSocket
from server_config import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title='Vegas Data Display')

def listen_for_display_clients(port_number):

    # configure the logger
    logging.basicConfig(filename="/home/sandboxes/jmasters/display_PRODUCTION/vegasrtdd-server/vegas_display_server.log",
                        format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=logging.INFO)
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

    application.listen(port_number) #, '0.0.0.0')
    try:
        logging.info('start ioloop listenting to port {}'.format(port_number))
        tornado.ioloop.IOLoop.instance().start()
        logginginfo('left ioloop')
    except KeyboardInterrupt:
        sys.exit()

if __name__ == "__main__":

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="the port number to use on the server", type=int)
    args = parser.parse_args()

    # Handle requests from clients to pass data from the stream
    listen_for_display_clients(args.port)
