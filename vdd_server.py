import zmq
from zmq.eventloop import zmqstream

import PBVegasData_pb2
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

import numpy as np

from tornado import websocket
import tornado.web
import tornado.ioloop

from multiprocessing import Process
import pickle
import time
import os
import sys
import signal # for timeout
import subprocess

UPDATE_INTERVAL = 1 # seconds
NCHANS = 512  # number of channels for client to display

def timeout_handler(signum, frame):
    raise 

banks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

def connect_to_bank(bank, bank_url, publisher_socket, client_socket):
    """Connect (i.e. subscribe) to a data publisher.

    Arguments:
    bank -- the name of the bank (e.g. 'A')
    bank_url -- the publishing address of the bank
    publisher_socket -- the publisher socket object, from ZMA.Socket().Context()
    client_socket -- from ZMQSocket class in this file

    """
    
    publisher_socket.connect(bank_url)

    def handler(msg):
        print('received data from VEGAS manager')
        # the following will eventually read a protobuf instead of a zmq
        # python object
        p = PBVegasData_pb2.pbVegasData()   # use this class to parse the protobuf
        p.ParseFromString(msg)

        # the following message goes to the JS client
        print 'length of VEGAS data:' + str(len(list(p.data)))
        client_socket.write_message(['data',p.data])

    for x in range(10000):
        publisher_socket.send('VEGAS.' + bank + ':Data')

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(3)
        try:
            # first recv() returns the key back
            print 'key from VEGAS is:' + publisher_socket.recv()
            handler(publisher_socket.recv())  # next recv() gets the protobuf
        except:
            print 'ERROR: did not get a response from bank', firstavailable, 'manager.'
            sys.exit()
        signal.alarm(0)

        time.sleep(UPDATE_INTERVAL)


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')
      
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        """
        This method is called when the JS creates a WebSocket object.
        """
        self.times = {}
        self.msgSize = None
        self.nSpecInAve = None
        self.specAve = None # running average of spectra
        self.publisher_socket = None

        context = zmq.Context(1)
        req_url = get_directory_endpoints('request')

        self.urls = {}
        for bank in banks:
            url = get_service_endpoints(context, req_url, 'VEGAS', 'Bank'+bank+'Mgr', 1)
            if 'NOT FOUND!' == url:
                print 'Bank ' + bank + ' is not available.'
            else:
                print 'Bank ' + bank + ' is AVAILABLE.'
                urls[bank] = url;

        if not self.urls:
            print 'ERROR: could not find available VEGAS banks'
            subprocess.call('list_all_services.py')
            sys.exit()
        else:
            # tell the client what banks are available to enable radio buttons
            ws.write_message(['bank_config', self.urls.keys()])

        ctx = zmq.Context()
        self.publisher_socket = ctx.socket(zmq.REQ)

        bank = self.urls.keys()[0]
        print 'Connecting to VEGAS bank', bank

        bank_url = self.urls[firstavailable]

 
        #  Also, call client to subscribe to the zmq socket. NOTICE: we
        #  additionally pass in a reference to self (ZMQWebSocket instance).
        connect_to_bank(bank, bank_url, self.publisher_socket, self)

    def on_message(self, bank):
        """
        This method is called when the server responds.  See send call in the
        onmessage function in Display.js in the client code.
        """
        print 'Connecting to bank ' + bank
        bank_url = self.urls[bank]

        connect_to_bank(bank, bank_url, self.publisher_socket, self)

    def write_message(self, msg):
        """ 
        The following extends the write_message() method of the
        websocket.WebSocketHandler() base class [using super()]
        with the preamble code that converts the message to unicode,
        sets the message size and records timing information.

        write_message is invoked by the write_message() call in connect_to_bank()
        
        """

        if not msg:
            print 'There is no message to write.  Quitting.'
            sys.exit()
        elif 'data' == msg[0]:
            npmsg = np.array(msg[1])
            rebinned_data = [np.mean(x) for x in npmsg.reshape((NCHANS,len(npmsg)/NCHANS))]
            data = unicode([msg[0], rebinned_data, np.floor(min(rebinned_data)), np.ceil(max(rebinned_data))])
        elif 'bank_config' == msg[0]:
            print repr(msg)
            data = repr(msg)
        else:
            print repr(msg)
            data = repr(msg)

        # the size of an 8bit Unicode string in bytes is length *2
        # the following is an idiom for
        # if x then do y, else no change (set x=x)
        self.msgSize = self.msgSize or len(data) * 2
               
        # the following line sends the data to the JS client
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)

    def on_close(self):
        print "WebSocket closed"

if __name__ == "__main__":

    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }

    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/websocket", ZMQWebSocket)
    ], **settings)
    
    application.listen(8889,'0.0.0.0')
    try:
        tornado.ioloop.IOLoop.instance().start()
    except(KeyboardInterrupt):
        sys.exit()

