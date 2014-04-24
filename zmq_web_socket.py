from server_config import *

from tornado import websocket

import zmq
from zmq.eventloop import zmqstream

from time import strftime, sleep
import threading
import numpy as np
import time
import sys
import json

from data_retriever import DataRetriever
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

class ZMQWebSocket(websocket.WebSocketHandler):

    connections = []
    data = [None]
    server_thread = []
    requesting_data = True

    def stop_requesting(self,):
        self.requesting_data = False

    def query_vegas_managers(self,):
        """Start up the server that reads spectra from the VEGAS manger

        This server reads from the VEGAS manager, as long as there is
        at least one browser connection, and serves it up to
        the display clients.

        """

        vegasReader = VEGASReader()

        # send message to client about what banks are active
        banks = {'A':True, 'B':True, 'C':True, 'D':True, 
                 'E':True, 'F':True, 'G':True, 'H':True}

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
                                                  major_key[b], minor_key[b], 
                                                  SERV_SNAPSHOT)
    
        while self.requesting_data:
            all_banks_spectra = []
            metadata = []
            first_bank = True
            for current_bank in banks.keys():
                if DEBUG:
                    print 'Requesting data for bank', current_bank
    
                if DEBUG:
                    print 'directory_url', directory_url
                    print 'device_url', device_url

                response = vegasReader.get_data_sample(current_bank, context, 
                                                       device_url[current_bank],
                                                       major_key[current_bank], 
                                                       minor_key[current_bank])
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
                        metadata = [project, scan, state, 
                                    integration, update_waterfall]
                        first_bank = False

                all_banks_spectra.append(spectrum)
    
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
            t = threading.Thread(target=self.query_vegas_managers)
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
        if not msg:
            print 'There is no message to write.  Quitting.'
            sys.exit()

        elif 'data' == msg[0]:
            command_to_client = msg[0]
            waterfall_bank = str(msg[1])
            metadata =  msg[2] # proj, scan, state, integration, update_waterfall
            rebinned_spectra = msg[3]

            colormin = np.floor(min(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            colormax = np.ceil(max(rebinned_spectra[ BANK_NUM[waterfall_bank] ]))
            color_limits = [colormin, colormax]

            data_to_send = [command_to_client, waterfall_bank,
                            metadata, color_limits, rebinned_spectra]
            if DEBUG:
                print ('sending', command_to_client, waterfall_bank, 
                       metadata, color_limits)

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

