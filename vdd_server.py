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

SERVER_AVAILABLE = True 

def timeout_handler(signum, frame):
    raise 

if SERVER_AVAILABLE:
    PUBLISHER_PORT = True
    banks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
else:
    from mock_zmq_publisher import mock_zmq_publisher
    PUBLISHER_PORT  = '5559'

def zmqclient(port_sub, ws):

    ctx = zmq.Context()
    
    if SERVER_AVAILABLE:

        context = zmq.Context(1)
        req_url = get_directory_endpoints('request')

        urls = {}
        for bank in banks:
            url = get_service_endpoints(context, req_url, 'VEGAS', 'Bank'+bank+'Mgr', 1)
            if 'NOT FOUND!' == url:
                print 'Bank ' + bank + ' is not available.'
            else:
                print 'Bank ' + bank + ' is AVAILABLE.'
                urls[bank] = url;

        if not urls:
            print 'ERROR: could not find available VEGAS banks'
            subprocess.call('list_all_services.py')
            sys.exit()

        snapshot_socket = ctx.socket(zmq.REQ)
        firstavailable = urls.keys()[0]
        print 'Connecting to VEGAS bank', firstavailable
        snapshot_socket.connect(urls[firstavailable])
    else:
        socket_sub = ctx.socket(zmq.SUB)
        socket_sub.connect ("tcp://localhost:%s" % port_sub)
        socket_sub.setsockopt(zmq.SUBSCRIBE, '')
        
    def handler(msg):
        if SERVER_AVAILABLE:
            print('received data from VEGAS manager')
            # the following will eventually read a protobuf instead of a zmq
            # python object
            p = PBVegasData_pb2.pbVegasData()   # use this class to parse the protobuf
            p.ParseFromString(msg)

            # the following message goes to the JS client
            print 'length of VEGAS data:' + str(len(list(p.data)))
            ws.write_message(p.data)
        else:
            # the following will eventually read a protobuf instead of a zmq
            # python object
            msg = pickle.loads(msg[0])
            ws.write_message(msg)

    if SERVER_AVAILABLE:
        for x in range(10000):
            snapshot_socket.send('VEGAS.'+bank+':Data')

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(3)
            try:
                print 'key from VEGAS is:' + snapshot_socket.recv()  # first recv() returns the key back
                handler(snapshot_socket.recv())  # next recv() gets the protobuf
            except:
                print 'ERROR: did not get a response from bank', bank, 'manager.'
                sys.exit()
            signal.alarm(0)

            time.sleep(1)
    else:
        stream_sub = zmqstream.ZMQStream(socket_sub)
        stream_sub.on_recv(handler)
        print "Connected to publisher with port %s" % port_sub


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

        if not SERVER_AVAILABLE:
            #  Launch our mock up zmq publisher in a separate process.
            Process(target=mock_zmq_publisher, args=(PUBLISHER_PORT,)).start()

        #  Also, call client to subscribe to the zmq socket. NOTICE: we
        #  additionally pass in a reference to self (ZMQWebSocket instance).
        zmqclient(PUBLISHER_PORT, self)
        print "WebSocket opened"

    def on_message(self, message):
        """
        This method is called when the server responds.  See send call in the
        onmessage function in Display.js in the client code.
        """
        # self.times[int(message)].append(time.time())
        print('got message', message)

    def write_message(self, msg):
        """ 
        The following extends the write_message() method of the
        websocket.WebSocketHandler() base class [using super()]
        with the preamble code that converts the message to unicode,
        sets the message size and records timing information.
        
        """

        nchans = 512

        # get a running average of the spectra
#            if self.specAve != None:
#                self.specAve = (self.specAve + msg) / self.nSpecInAve
#                self.nSpecInAve += 1
#            else:
#                self.specAve = np.array(msg)
#                self.nSpecInAve = 1

        if not msg:
            print 'There is no message to write.  Quitting.'
            sys.exit()
        elif 'close' != msg:
            npmsg = np.array(msg)
            rebinned_data = [np.mean(x) for x in npmsg.reshape((nchans,len(npmsg)/nchans))]
            data = unicode([rebinned_data, np.floor(min(rebinned_data)), np.ceil(max(rebinned_data))])
            # self.times[msg[0]] = [time.time()]
        else:
            print msg
            data = msg

        # the size of an 8bit Unicode string in bytes is length *2
        # the following is an idiom for
        # if x then do y, else no change (set x=x)
        self.msgSize = self.msgSize or len(data) * 2
               
        # the following line sends the data to the JS client
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)

    def on_close(self):
        print "WebSocket closed"
        #print "Message size (bytes)", self.msgSize
        #print [e - s for _ , (s, e) in self.times.iteritems()]

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

