import tornado.web
import tornado.ioloop

import os
import sys
import logging
import argparse
import signal
import time

from zmq_web_socket import ZMQWebSocket
from server_config import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title='Vegas Data Display')

def listen_for_display_clients(port):

    # configure the logger
    logfile="/home/sandboxes/jmasters/display_PRODUCTION/vegasrtdd-server/vegas_display_server.log"
    logging.basicConfig(filename=logfile,
                        format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=logging.INFO)

    # tornado http server settings
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }

    # define tornado sever application
    application = tornado.web.Application([
         # when someone goes to the main page url:port
         # invoke MainHandler, which loads html that loads Display.js,
         # which opens url:port/websocket that invokes ZMQWebSocket
        (r"/", MainHandler),
        (r"/websocket", ZMQWebSocket)
    ], **settings)

    application.listen(port)

    # signal handler
    def sig_handler(sig, frame):
        logging.warning("Caught signal {}".format(sig))
        tornado.ioloop.IOLoop.instance().stop()
    
    # signal register
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    logging.info('Starting HttpServer listenting to port {}'.format(port))
    tornado.ioloop.IOLoop.instance().start()
    logging.info('Exit...')

if __name__ == "__main__":

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="the port number to use on the server", type=int)
    args = parser.parse_args()

    # Handle requests from clients to pass data from the stream
    listen_for_display_clients(args.port)
