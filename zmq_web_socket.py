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

from vegas_reader import VEGASReader

class ZMQWebSocket(websocket.WebSocketHandler):

    connections = []
    data = [None]
    server_thread = []
    requesting_data = True
    vegasReader = None

    def query_vegas_managers(self,):
        """Start up the server that reads spectra from the VEGAS manger

        This server reads from the VEGAS manager, as long as there is
        at least one browser connection, and serves it up to
        the display clients.

        """

        if DEBUG: print 'querying vegas managers'

        self.vegasReader = VEGASReader()

        # continually request data from the VEGAS manager, so long as there
        #  is at least one browser connection
        while self.requesting_data:

            all_banks_spectra, metadata = [], []
            first_bank = True

            # request data for each of the banks (A-H)
            for bank in self.vegasReader.banks:
                
                if bank not in self.vegasReader.active_banks:
                    if UPDATES_DEBUG: print 'writing zeros for',bank
                    spectrum = np.zeros((1,NCHANS)).tolist()

                # structure of response is:
                #
                #  result_state (e.g. 'ok' 'same' 'error)
                #  spectrum
                #  project
                #  scan
                #  state
                #  integration
                #
                try:
                    response = self.vegasReader.get_data_sample(bank)
                except:
                    if UPDATES_DEBUG: print 'ERROR getting data sample', sys.exc_info()[0]
                    response = ['error']

                if response[0] == 'error':
                    if UPDATES_DEBUG: print 'writing zeros for',bank
                    spectrum = np.zeros((1,NCHANS)).tolist()

                else:
                    spectrum = response[1]

                    # if spectrum is a numpy array, convert it to a list
                    if type(spectrum) != type([]) and hasattr(spectrum, "tolist"):
                        spectrum = spectrum.tolist()

                    # get metadata from the first bank
                    if first_bank:
                        project, scan, state, integration = response[2:]
                        if response[0] == 'same':
                            update_waterfall = 0
                        else:
                            update_waterfall = 1

                        update_waterfall = 1
                        metadata = [project, scan, state, integration, update_waterfall]
                        first_bank = False

                all_banks_spectra.append(spectrum)

            # by setting self.data we allow on_message to
            #  write a message back to the client
            self.data[0] = [metadata, all_banks_spectra]

            if UPDATES_DEBUG:  print strftime("%H:%M:%S")
            sleep(.300)

    def open(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        if DEBUG: print 'SOCKET OPENED'

        # Start service that reads spectra from manager
        if not self.server_thread:

            if DEBUG: print 'starting display server'
            t = threading.Thread(target=self.query_vegas_managers)
            self.server_thread.append(t)
            self.server_thread[0].start()

        self.connections.append(self)
        print "Connections:", len(self.connections), self.connections

    def on_message(self, request_from_client):
        """Handle message from client.

        This method is called when the client responds at the end of
        the bank_config step in Display.js.

        """

        if UPDATES_DEBUG:
            print 'got a message from the client!', self
            print 'Client is requesting', request_from_client

        if request_from_client == "active_banks":
            # send message to client about what banks are active
            message = ['bank_config', ['A','B','C','D','E','F','G','H']]#self.vegasReader.active_banks]

        else:
            waterfall_bank = request_from_client

            # check that the VEGASReader got something from the
            #   manager and put it in the self.data buffer
            if self.data[0]:
                if DEBUG: print 'we have data', self
                metadata = self.data[0][0]
                spectra = self.data[0][1]

                for idx,x in enumerate(spectra):
                    if type(x) == type(np.ones(1)):
                        spectra[idx] = spectra[idx].tolist()

                message = ['data', str(waterfall_bank), metadata, spectra]
            else:
                message = ['error']

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

        if 'data' == msg[0]:
            try:
                data = json.dumps(msg)
            except TypeError:
                if DEBUG: print 'FOUND A NUMPY ARRAY!'
                if DEBUG: print type(msg[3][0])
                sys.exit()

        elif 'bank_config' == msg[0]:
            if DEBUG:
                print repr(msg)
            data = repr(msg)

        else:
            if UPDATES_DEBUG: print repr(msg)
            data = repr(msg)

        # the following line sends the data to the JS client
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)

    def on_close(self):

        if self.connections:
            self.connections.pop()

        else:
            self.requesting_data = False

        print "Connections:", len(self.connections)
