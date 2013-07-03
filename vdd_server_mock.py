import zmq
from zmq.eventloop import zmqstream

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

from mock_zmq_publisher import mock_zmq_publisher
PUBLISHER_PORT  = {'A': '5551',
                   'B': '5552',
                   'C': '5553',
                   'D': '5554',
                   'E': '5555',
                   'F': '5556',
                   'G': '5557',
                   'G': '5558'}
ACTIVE_MOCK_BANKS = ['A', 'B']

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
        # The mock server uses a pickled python object, while the vegas
        #  server uses a protobuf
        msg = pickle.loads(msg)
        client_socket.write_message(['data',msg])

    publisher_socket.send('')
    message = publisher_socket.recv()
    handler(message)
    print "Got data from bank %s, port %s" % (bank, PUBLISHER_PORT[bank])

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

        #  Launch our mock up zmq publishers in separate processes.
        for bb in ACTIVE_MOCK_BANKS:
            print 'Bank',bb,'Port',PUBLISHER_PORT[bb]
            Process(target=mock_zmq_publisher, args=(PUBLISHER_PORT[bb],)).start()

        ctx = zmq.Context()
        self.publisher_socket = ctx.socket(zmq.REQ)

        # send message to client about what banks are active
        self.write_message(['bank_config', ACTIVE_MOCK_BANKS]);
        
    def on_message(self, bank):
        """
        This method is called when the server responds.  See send call in the
        onmessage function in Display.js in the client code.

        """
        print 'Getting data from bank ' + bank
        bank_url = "tcp://localhost:%s" % PUBLISHER_PORT[bank]

        #  NB: we additionally pass in a reference to self (ZMQWebSocket instance).
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

