import zmq
from zmq.eventloop import zmqstream

import numpy as np
import pylab as pl

from tornado import websocket
import tornado.web
import tornado.ioloop

import multiprocessing
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

from pprint import pprint
import pdb

from DataStreamUtils import get_service_endpoints, get_directory_endpoints

DEBUG = True
LIVETEST = False
BANK_NUM = {'A':0, 'B':1, 'C':2, 'D':3,
            'E':4, 'F':5, 'G':6, 'H':7}

NS_REGISTER = 0
NS_REQUEST = 1
NS_PUBLISHER = 2

SERV_PUBLISHER = 0
SERV_SNAPSHOT = 1
SERV_CONTROL = 2

NCHANS = 512  # number of channels for client to display
BUFFER_SIZE = 600 # num of spectra to store at full res for each bank

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')

class DataRetriever():
    def __init__(self,):
        self.previous_scan = None
        self.previous_integration = None

    def handle_response(self, manager_response):
        el = len(manager_response)

        if el == 1:  # Got an error
            if manager_response[0] == "E_NOKEY":
                print "No key/value pair found on server!"
                return None
        elif el > 1:
            # first element is the key
            # the following elements are the values
                #print manager_response
            key = manager_response[0]

            if not key.endswith("Data"):
                df = PBDataField()
                df.ParseFromString(manager_response[1])
                if key.endswith("state"):
                    response = str(df.val_struct[0].val_string[0])
                if DEBUG:
                    print df.name, '=', response
                return response
            else:
                df = pbVegasData()
                df.ParseFromString(manager_response[1])
                #pdb.set_trace()
                if DEBUG:
                    print 'project: ', df.project_id
                    print 'scan: ', df.scan_number
                    print "integration: ", df.integration
                    print "time: ", df.time
                    print "cals: ", df.cal_state
                    print "sig_ref: ", df.sig_ref_state
                    print "data_dims: ", df.data_dims
                    print "data[:8]: ", df.data[:8]

                arr = np.array(df.data)
                dims = df.data_dims[::-1]
                arr = arr.reshape(dims)
                spectrum = arr[0,0,:]
    
                if DEBUG:
                    print 'max in arr', np.max(arr)
                    print 'min in arr', np.min(arr)
                    print 'mean in arr', np.mean(arr)
                    print 'max in spectrum', np.max(spectrum)
                    print 'ptp in spectrum', np.ptp(spectrum)
    
                project = str(df.project_id)
                scan = int(df.scan_number)
                integration = int(df.integration)
                response = (scan, project, spectrum, integration)
                return response
        else:
            return None

    def get_data_sample(self, bank, client_socket):
        """Connect (i.e. subscribe) to a data publisher.

        Arguments:
        bank -- the name of the bank (e.g. 'A')
        client_socket -- from ZMQSocket class in this file

        """
        context = zmq.Context()
        if LIVETEST:
            major_key = "VEGAS"
            minor_key = "Bank{0}Mgr".format(bank)
        else:
            major_key = "VegasTest"
            minor_key = major_key + bank

        dataKey = "%s.%s:Data" % (major_key, minor_key)
        stateKey = "%s.%s:P:state" % (major_key, minor_key)

        directory_url = get_directory_endpoints("request")
        device_url = get_service_endpoints(context, directory_url,
                                           major_key, minor_key, SERV_SNAPSHOT)

        request_url = context.socket(zmq.REQ)
        if 'NOT FOUND' in device_url:
            print 'Bank', bank, device_url
            # client_socket.write_message(['error', bank])
            return ['error']
        else:
            request_url.connect(device_url)

            if DEBUG:
                print '------------'
    
            request_url.send(str(stateKey))
            response = request_url.recv_multipart()
            state = self.handle_response(response)

            if "Committed" == state or "Running" == state:
                request_url.send(str(dataKey))
                response = request_url.recv_multipart()

                scan, project, spectrum, integration = self.handle_response(response)
                if DEBUG:
                    print "scan {0} ~ prevscan {1} int {2} ~ prevint {3}\n\n".format(scan,self.previous_scan,integration,self.previous_integration)
                if scan != self.previous_scan or integration != self.previous_integration:
                    self.previous_scan = scan
                    self.previous_integration = integration
                    return ['ok', spectrum, project, scan, state, integration]
                else:
                    print "Scan and integration numbers haven't changed for bank {2}. Integration: {0} Bank: {1}".format(scan,integration,bank)
#                    return ['same']
                    return ['ok', spectrum, project, scan, state, integration]
            else:
                return ['error']

class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        def default_factory():
            return deque(maxlen=BUFFER_SIZE)
        self.databuffer = defaultdict(default_factory)
        self.messageRetriever = DataRetriever()

        self.msgSize = None
        self.nSpecInAve = None
        self.specAve = None # running average of spectra
        self.publisher_socket = None
        self.active_banks = None

        # send message to client about what banks are active
        self.banks = {'A':True, 'B':True, 'C':True, 'D':True, 'E':True, 'F':True, 'G':True, 'H':True}

        for bank in self.banks.keys():
            context = zmq.Context()
            if LIVETEST:
                major_key = "VEGAS"
                minor_key = "Bank{0}Mgr".format(bank)
            else:
                major_key = "VegasTest"
                minor_key = major_key + bank

            stateKey = "%s.%s:P:state" % (major_key, minor_key)

            directory_url = get_directory_endpoints("request")
            device_url = get_service_endpoints(context, directory_url,
                                               major_key, minor_key, SERV_SNAPSHOT)

            request_url = context.socket(zmq.REQ)
            if 'NOT FOUND' in device_url:
                print 'Bank', bank, device_url
                self.banks[bank] = False
        
        self.active_banks = [b for b in self.banks if self.banks[b]]
        print 'Active banks',self.active_banks
        self.write_message(['bank_config', self.active_banks])

    def on_message(self, waterfall_bank):
        """Handle message from client.

        This method is called when the client responds at the end of
        the bank_config step in Display.js.

        """
        print '------------'
        print 'Requesting BANK', waterfall_bank
        print '------------'

        all_banks_spectra = []
        metadata = []
        pids = [] # process ids for parallel processing
        result_queue = multiprocessing.Queue()
        for b in self.banks:
#            if self.banks[b]:
#                p = multiprocessing.Process(target=self.messageRetriever.get_data_sample,
#                                            args=(b, self,))
#                pids.append(p)
            response = self.messageRetriever.get_data_sample(b, self)
            if response[0] == 'ok':
                spectrum = response[1]
                if b == waterfall_bank:
                    project, scan, state, integration = response[2:]
                    metadata = [project, scan, state, integration]
            else:
                spectrum = np.zeros(NCHANS)
#            else:
#                spectrum = np.zeros(NCHANS)

            all_banks_spectra.append(spectrum)

        self.write_message(['data', waterfall_bank, metadata, all_banks_spectra])

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
            command_to_client = msg[0]
            waterfall_bank = str(msg[1])
            metadata =  msg[2] # proj, scan, state, integration
            all_banks_spectra = msg[3]

            # self.databuffer[bank].append(spectrum)

            rebinned_spectra = []
            for spectrum in all_banks_spectra:
                rebinned_spectrum = [np.mean(x) 
                                     for x 
                                     in spectrum.reshape((NCHANS,len(spectrum)/NCHANS))]
                rebinned_spectra.append(rebinned_spectrum)

            colormin = np.floor(min(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            colormax = np.ceil(max(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            color_limits = [colormin, colormax]

            data_to_send = [command_to_client, waterfall_bank, metadata, color_limits, rebinned_spectra]
            print 'sending', command_to_client, waterfall_bank, metadata, color_limits

            if DEBUG:
                for idx,dd in enumerate(data_to_send):
                    print idx,type(dd)

            # we send the data to the client as a unicode string
            data = unicode(data_to_send)

        elif 'bank_config' == msg[0]:
            if DEBUG:
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

