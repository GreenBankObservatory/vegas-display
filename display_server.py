#!/usr/bin/env python
import web
import sys
import argparse
import signal
import logging
import threading
import os

# Uncomment the next line for PRODUCTION
# Also, see the application line below with wsgifunc()
# web.config.debug = False

urls = ('/', 'Banks', '/windows', 'Windows', '/waterfall', 'Waterfall')
template_dir = os.path.abspath(os.path.dirname(__file__)) + '/templates'
render = web.template.render(template_dir, cache=False)
# Uncomment .wsgifunc() in the next line for PRODUCTION
application = web.application(urls, globals())  # .wsgifunc()

# configure the logger
log_level = {"err":   logging.ERROR,
             "warn":  logging.WARNING,
             "info":  logging.INFO,
             "debug": logging.DEBUG}


class Banks:
    def GET(self):
        print 'banks request!!!'
        web.header('Content-Type', 'text/html')
        return render.banks()


class Windows:
    def GET(self):
        print 'windows request!!!'
        web.header('Content-Type', 'text/html')
        winp = web.input()
        print winp
        return render.windows(winp.bank)


class Waterfall:
    def GET(self):
        print 'waterfall request!!!'
        web.header('Content-Type', 'text/html')
        winp = web.input()
        print winp
        return render.waterfall(winp.bank, winp.window)

if __name__ == "__main__":

    # signal handler
    def sig_handler(sig, _):
        logging.warning("Caught signal {}".format(sig))
        logging.warning("Shutting down server...")
        application.stop()
    
    # signal register
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="port number to use on the server", type=int)
    args = parser.parse_args()
    application.run()
