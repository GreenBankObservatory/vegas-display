import zmq
from zmq.eventloop import zmqstream
import random
import numpy as np
import pylab as pl

from tornado import websocket
import tornado.web
import tornado.ioloop

from time import strftime,sleep
import multiprocessing
import threading
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
import json

from pprint import pprint
import pdb
from random import randint
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

DO_PARSE = True
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
        self.prev_scan = None
        self.prev_integration = None

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
                if DO_PARSE:
                    df = pbVegasData()
                    t = threading.Thread(target=df.ParseFromString, args=(manager_response[1],))
                    t.start()
                    t.join()
                else:
                    class DF:
                        project_id = 'ProjectFOO'
                        scan_number = random.randint(0,9999)
                        integration = random.randint(0,9999)
                        time = 100
                        cal_state = None
                        sig_ref_state = None
                        data_dims = 1024
                        data = np.random.random(1024)

                    df = DF()

                n_sig_states = len(set(df.sig_ref_state))
                n_cal_states = len(set(df.cal_state))
                n_subbands = len(set(df.subband))
                n_chans, n_samplers, n_states = df.data_dims
                if DEBUG:
                    print 'project: ', df.project_id
                    print 'scan: ', df.scan_number
                    print "integration: ", df.integration
                    print "time: ", df.time
                    print "cals: ", n_cal_states
                    print "sig_ref: ", n_sig_states
                    print "data_dims: ", df.data_dims
                    print "data[:8]: ", df.data[:8]
                    print "subbands: ", n_subbands
                    print "dims: ", n_chans, n_samplers, n_states

                arr = np.array(df.data)
                if DO_PARSE:
                    arr = arr.reshape(df.data_dims[::-1])
                    # average the cal-on/off pairs
                    # this reduces the second dimension by 1/2
                    # i.e. 2,14,1024 becomes 2,7,1024

                    n_skip = (n_samplers/n_subbands)
                    if DEBUG:
                        print 'skip every ', n_skip
                        
                    if n_sig_states == 1:
                        # assumes no SIG switching
#                        arr = np.mean((arr[:,:,::2], arr[:,:,1::2]), axis=1)
                        arr = np.mean(arr, axis=0)
                        
                        spectrum = arr[::n_skip,:].ravel()
                    else:
                        # just show the first states
                        spectrum = arr[0,::n_skip,:].ravel()
                        
                    #pdb.set_trace()
                    # normalize by dividing by integration time
                    # !!! the following line needs to be smarter.   we need to choose the appropriate
                    # !!! integration times instead of simply the first one in the array, but this
                    # !!! is a good approximation of normalizing the data
                    # !!! soon, the manager will be streaming normalized data anyway and this step
                    # !!! will not be needed
                    spectrum = spectrum / df.integration_time[0]
                else:
                    spectrum = arr
    
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

    def get_data_sample(self, bank, context, device_url, major_key, minor_key):
        """Connect (i.e. subscribe) to a data publisher.

        Arguments:
        bank -- the name of the bank (e.g. 'A')

        """
        if 'NOT FOUND' in device_url:
            print 'Bank', bank, device_url
            return ['error']
        else:
            request_url = context.socket(zmq.REQ)
            request_url.connect(device_url)

            if DEBUG:
                print '------------'
    
            dataKey = "%s.%s:Data" % (major_key, minor_key)
            stateKey = "%s.%s:P:state" % (major_key, minor_key)

            request_url.send(str(stateKey))
            response = request_url.recv_multipart()
            state = self.handle_response(response)

            if "Committed" == state or "Running" == state:
                request_url.send(str(dataKey))
                response = request_url.recv_multipart()

                self.handle_response(response)
                scan, project, spectrum, integration = self.handle_response(response)
                if DEBUG:
                    print "scan {0} ~ prevscan {1} int {2} ~ prevint {3}\n\n".format(scan,
                                                                                     self.prev_scan,
                                                                                     integration,
                                                                                     self.prev_integration)
                # if something changed
                if scan != self.prev_scan or integration != self.prev_integration:
                    self.prev_scan = scan
                    self.prev_integration = integration
                    return ['ok', spectrum, project, scan, state, integration]
                else:  # if nothing changed
                    if DEBUG:
                        print "Scan and integration numbers haven't changed for ",
                        print "bank {2}. Integration: {0} Bank: {1}".format(scan,integration,bank)
                    return ['same', spectrum, project, scan, state, integration]
            else:
                return ['error']

class ZMQWebSocket(websocket.WebSocketHandler):

    connections = []
    data = [None]
    server_thread = []
    requesting_data = True

    def stop_requesting(self,):
        self.requesting_data = False

    def run_display_server(self,):
        """Start up the server that reads spectra from the VEGAS manger

        This server reads from the VEGAS manager and serves it up to
        the display client.

        """

        def default_factory():
            return deque(maxlen=BUFFER_SIZE)

        databuffer = defaultdict(default_factory)
        messageRetriever = DataRetriever()

        nSpecInAve = None
        specAve = None # running average of spectra
        publisher_socket = None
        active_banks = None
    
        # send message to client about what banks are active
        banks = {'A':True, 'B':True, 'C':True, 'D':True, 'E':True, 'F':True, 'G':True, 'H':True}

        directory_url = get_directory_endpoints("request")
        context = zmq.Context()
    
        device_url = {}
        major_key = {}
        minor_key = {}
        for b in banks.keys():
            if LIVETEST:
                major_key[b] = "VEGAS"
                minor_key[b] = "Bank{0}Mgr".format(b)
            else:
                major_key[b] = "VegasTest"
                minor_key[b] = major_key[b] + b

            device_url[b] = get_service_endpoints(context, directory_url,
                                                  major_key[b], minor_key[b], SERV_SNAPSHOT)
    
        while self.requesting_data:
            all_banks_spectra = []
            metadata = []
            first_bank = True
            for b in banks.keys():
                if DEBUG:
                    print 'Requesting data for bank', b
    
                if DEBUG:
                    print 'directory_url', directory_url
                    print 'device_url', device_url

                response = messageRetriever.get_data_sample(b, context, device_url[b],
                                                            major_key[b], minor_key[b])
                if response[0] == 'error':
                    spectrum = np.zeros(NCHANS)
                else:
                    spectrum = response[1]
                    if first_bank: # only use the metadata from first bank
                        project, scan, state, integration = response[2:]
                        if response[0] == 'same':
                            update_waterfall = 0
                        else:
                            update_waterfall = 1
                        metadata = [project, scan, state, integration, update_waterfall]
                        first_bank = False

                all_banks_spectra.append(spectrum)
    
            if DEBUG:
                print 'nspectra',len(all_banks_spectra)

            self.data[0] = [metadata, all_banks_spectra]
            if DEBUG:
                print strftime("%H:%M:%S")
            sleep(.300)


    def initialize(self):
        print '\n\nINITIALIZING!!!\n\n'

    def open(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        print 'SOCKET OPENED'

        if not self.connections:
            # Start service that reads spectra from manager
            #
            print 'starting display server'
            t = threading.Thread(target=self.run_display_server)
            self.server_thread.append(t)
            self.server_thread[0].start()
            print 'done'
        self.connections.append(self)
        print "Connections:", len(self.connections), self.connections

    def on_message(self, waterfall_bank):
        """Handle message from client.

        This method is called when the client responds at the end of
        the bank_config step in Display.js.

        """
        print 'GOT A MESSAGE FROM THE CLIENT!', self

        if self.data[0]:
            print 'we have data', self
            metadata = self.data[0][0]
            spectra = self.data[0][1]
            message = ['data', str(waterfall_bank), metadata, spectra]
            self.write_message(message)

    def write_message(self, msg):
        """Send a message to the client.

        This method extends the write_message() method of the
        websocket.WebSocketHandler() base class [using super()] with
        the preamble code that converts the message to unicode, sets
        the message size and records timing information.

        write_message is invoked by the write_message() call in
        get_data_sample() or socket open() on socket creation.

        """
        if DEBUG:
            print 'GETTING READY TO RESPOND'

        if not msg:
            print 'There is no message to write.  Quitting.'
            sys.exit()

        elif 'data' == msg[0]:
            command_to_client = msg[0]
            waterfall_bank = str(msg[1])
            metadata =  msg[2] # proj, scan, state, integration, update_waterfall
            all_banks_spectra = msg[3]

            rebinned_spectra = []
            for spectrum in all_banks_spectra:
                rebinned_spectrum = spectrum.reshape((NCHANS,len(spectrum)/NCHANS)).mean(axis=1).tolist()
                rebinned_spectra.append(rebinned_spectrum)

            colormin = np.floor(min(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            colormax = np.ceil(max(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            color_limits = [colormin, colormax]

            data_to_send = [command_to_client, waterfall_bank, metadata, color_limits, rebinned_spectra]
            if DEBUG:
                print 'sending', command_to_client, waterfall_bank, metadata, color_limits

            if DEBUG:
                for idx,dd in enumerate(data_to_send):
                    print idx,type(dd)

            # we send the data to the client as a unicode string
            #data = unicode(data_to_send)
            data = json.dumps(data_to_send)

        elif 'bank_config' == msg[0]:
            if DEBUG:
                print repr(msg)
            data = repr(msg)
        else:
            print repr(msg)
            data = repr(msg)

        # the following line sends the data to the JS client
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)

    def on_close(self):
        self.connections.pop()
        if not self.connections:
            self.stop_requesting()
            self.server_thread[0].join()
            self.server_thread.pop()
        print "WebSocket closed"
        print "Connections:", len(self.connections)

def listen_for_display_clients(port_number):
    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
    }

    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/websocket", ZMQWebSocket)
    ], **settings)

    print 'add listener'
    application.listen(port_number,'0.0.0.0')
    try:
        print 'start ioloop listenting to port', port_number
        tornado.ioloop.IOLoop.instance().start()
        print 'left ioloop'
    except(KeyboardInterrupt):
        sys.exit()


if __name__ == "__main__":

    # Handle requests from clients to pass data from the stream
    #
    listen_for_display_clients(7777)
