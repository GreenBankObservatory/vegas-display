import zmq
from zmq.eventloop import zmqstream

import numpy as np
import pylab as pl

from tornado import websocket
import tornado.web
import tornado.ioloop

from multiprocessing import Process
from collections import deque
from collections import defaultdict
import pickle
import time
import os
import sys
import signal # for timeout
import subprocess
from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *

from DataStreamUtils import get_service_endpoints, get_directory_endpoints

NS_REGISTER = 0
NS_REQUEST = 1
NS_PUBLISHER = 2

SERV_PUBLISHER = 0
SERV_SNAPSHOT = 1
SERV_CONTROL = 2

NCHANS = 512  # number of channels for client to display
ACTIVE_MOCK_BANKS = ['A','B']
BUFFER_SIZE = 600 # num of spectra to store at full res for each bank


def timeout_handler(signum, frame):
    raise

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')

def handle_response(manager_response):
    el = len(manager_response)


    if el == 1:  # Got an error
        if manager_response[0] == "E_NOKEY":
            print "No key/value pair %s found on server!" % (key)
            return None
    elif el > 1:
        # first element is the key
        # the following elements are the values
            #print manager_response
        key = manager_response[0]
        if not key.endswith("Data"):
            df = PBDataField()
            df.ParseFromString(manager_response[1])
            if key.endswith("projectId") or key.endswith("state"):
                response = str(df.val_struct[0].val_string[0])
            elif key.endswith("scanNumber"):
                response = int(df.val_struct[0].val_int64[0])
            print df.name, '=', response
            return response
        else:
            df = pbVegasData()
            df.ParseFromString(manager_response[1])
            print "time: ", df.time
            print "integration: ", df.integration
            print "cals: ", df.cal_state
            print "sig_ref: ", df.sig_ref_state
            print "data_dims: ", df.data_dims
            print "data[:8]: ", df.data[:8]
            arr = np.array(df.data)
            dims = df.data_dims[::-1]
            arr = arr.reshape(dims)
            spectrum = arr[0,0,:]
            integration = int(df.integration)
            response = (spectrum, integration)
            return response
    else:
        return None

def get_data_sample(bank, client_socket):
    """Connect (i.e. subscribe) to a data publisher.

    Arguments:
    bank -- the name of the bank (e.g. 'A')
    client_socket -- from ZMQSocket class in this file

    """
    context = zmq.Context(1)
    major_key = "VegasTest"
    minor_key = major_key + bank

    dataKey = "%s.%s:Data" % (major_key, minor_key)
    scanKey = "%s.%s:P:scanNumber" % (major_key, minor_key)
    stateKey = "%s.%s:P:state" % (major_key, minor_key)
    projKey = "%s.%s:P:projectId" % (major_key, minor_key)
    keys = [dataKey, scanKey, stateKey, projKey]

    directory_url = get_directory_endpoints("request")
    device_url = get_service_endpoints(context, directory_url,
                                       major_key, minor_key, SERV_SNAPSHOT)

    request_url = context.socket(zmq.REQ)
    if 'NOT FOUND' in device_url:
        print 'Bank', bank, device_url
        client_socket.write_message(['error'])
    else:
        request_url.connect(device_url)

        print '------------'
        request_url.send(str(projKey))
        response = request_url.recv_multipart()
        project = handle_response(response)

        request_url.send(str(scanKey))
        response = request_url.recv_multipart()
        scan = handle_response(response)

        request_url.send(str(stateKey))
        response = request_url.recv_multipart()
        state = handle_response(response)

        if "Committed" == state:
            request_url.send(str(dataKey))
            response = request_url.recv_multipart()
            spectrum, integration = handle_response(response)

            client_socket.write_message(['data', bank, project, scan, 
                                         state, integration, spectrum])

class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        def default_factory():
            return deque(maxlen=BUFFER_SIZE)
        self.databuffer = defaultdict(default_factory)

        self.msgSize = None
        self.nSpecInAve = None
        self.specAve = None # running average of spectra
        self.publisher_socket = None

        # send message to client about what banks are active
        self.write_message(['bank_config', ACTIVE_MOCK_BANKS]);

    def on_message(self, bank):
        """Handle message from client.

        This method is called when the client responds at the end of
        the bank_config step in Display.js.

        """
        print '--------------------\nGetting data from bank ' + bank

        #  NB: we additionally pass a reference to self (ZMQWebSocket instance).
        get_data_sample(str(bank), self)

    def write_message(self, msg):
        """Send a message to the client.

        This method extends the write_message() method of the
        websocket.WebSocketHandler() base class [using super()] with
        the preamble code that converts the message to unicode, sets
        the message size and records timing information.

        write_message is invoked by the write_message() call in
        get_data_sample() or socket open() on socket creation.

        """
        if not msg:
            print 'There is no message to write.  Quitting.'
            sys.exit()
        elif 'data' == msg[0]:
            bank, project, scan, state, integration, spectrum = msg[1:]
            self.databuffer[bank].append(spectrum)

            rebinned_data = [np.mean(x) 
                             for x 
                             in spectrum.reshape((NCHANS,len(spectrum)/NCHANS))]

            data_to_send = [msg[0], bank, project, scan, state, integration, rebinned_data,
                            np.floor(min(rebinned_data)),
                            np.ceil(max(rebinned_data))]

            for idx,dd in enumerate(data_to_send):
                print idx,type(dd)

            # we send the data to the client as a unicode string
            data = unicode(data_to_send)

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

