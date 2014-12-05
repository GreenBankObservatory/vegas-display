#!/usr/bin/env python
import web
import sys
import argparse
import signal
import logging
import threading

from makeplots import Plots

urls = ('/', 'Banks', '/windows', 'Windows', '/waterfall', 'Waterfall' )
render = web.template.render('templates/', cache=False)
app = web.application(urls, globals())

# configure the logger
log_level = {"err"  : logging.ERROR,
             "warn" : logging.WARNING,
             "info" : logging.INFO,
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
    def sig_handler(sig, frame):
        logging.warning("Caught signal {}".format(sig))
        logging.warning("Shutting down server...")
        app.stop()
    
    # signal register
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("port", help="port number to use on the server", type=int)
    args = parser.parse_args()
    app.run()
