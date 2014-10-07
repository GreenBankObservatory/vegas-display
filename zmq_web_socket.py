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
import logging

from vegas_reader import VEGASReader

class ZMQWebSocket(websocket.WebSocketHandler):

    connections = []
    data = None
    server_thread = None
    requesting_data = True
    vegasReader = None

    def query_vegas_managers(self,):
        """Start up the server that reads spectra from the VEGAS manger

        This server reads from the VEGAS manager, as long as there is
        at least one browser connection, and serves it up to
        the display clients.

        """

        logging.debug('querying vegas managers')

        ZMQWebSocket.vegasReader = VEGASReader()

        # continually request data from the VEGAS managers,
        # so long as there is at least one browser connection
        while self.requesting_data:

            all_banks_spectra, metadata = [], []
            have_metadata = False

            # request data for each of the banks (A-H)
            for bank in self.vegasReader.banks:
                
                if bank not in self.vegasReader.active_banks:
                    logging.debug('Bank {0} is not active.  '
                                  'Sending zeros to client'.format(bank))
                    spectrum = np.zeros((1,NCHANS)).tolist()

                else:
                    try:
                        # collect some data for the bank
                        response = self.vegasReader.get_data_sample(bank)
                        # structure of response is:
                        #
                        #  result_state (e.g. 'ok' 'same' 'error)
                        #  spectrum
                        #  project
                        #  scan
                        #  state
                        #  integration
                    except:
                        logging.debug('ERROR getting data sample {}'.format(sys.exc_info()))
                        response = ['error']

                    if response[0] == 'error' or response[0] == 'idle':
                        logging.debug('{0}: recording zeros for {1}'.format(response[0], bank))
                        spectrum = np.zeros((1,NCHANS)).tolist()

                    else:
                        spectrum = response[1]

                        # if spectrum is a numpy array, convert it to a list
                        if type(spectrum) != type([]) and hasattr(spectrum, "tolist"):
                            spectrum = spectrum.tolist()

                        # get metadata from the first bank
                        #  the metadata should be the same for all banks
                        #  !!! NB: I think we can remove 'state' as it is unique
                        #  !!! to the bank and seems to not be used
                        if not have_metadata:
                            project, scan, state, integration = response[2:]
                            if response[0] == 'same':
                                update_waterfall = 0
                            else:
                                update_waterfall = 1

                            update_waterfall = 1
                            metadata = [project, scan, state, integration, update_waterfall]
                            have_metadata = True

                all_banks_spectra.append(spectrum)

            # by setting self.data we allow on_message to
            #  write a message back to the client
            ZMQWebSocket.data = [metadata, all_banks_spectra]

            logging.debug(strftime("%H:%M:%S"))
            sleep(.800)

    def open(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        logging.debug('SOCKET OPENED')

        # Start service that reads spectra from manager
        if not self.server_thread:

            logging.info('starting display server')
            ZMQWebSocket.server_thread = threading.Thread(target=self.query_vegas_managers)
            self.server_thread.start()
            # give it a second to get started before looking for data
            sleep(1)

        self.connections.append(self)
        logging.info("Client browser socket connections: {}".format(len(self.connections)))

    def on_message(self, request_from_client):
        """Handle message from client.

        This method is called when the client responds at the end of
        the bank_config step in Display.js.

        """

        logging.debug('Client is requesting \'{0}\''.format(request_from_client))

        if request_from_client == "active_banks":
            # send message to client about what banks are active
            message = ['bank_config', self.vegasReader.active_banks]

        else:
            # check that the VEGASReader got something from the
            #   manager and put it in the self.data buffer
            if self.data:
                metadata = self.data[0]
                spectra = self.data[1]

                for idx,x in enumerate(spectra):
                    if type(x) == type(np.ones(1)):
                        spectra[idx] = spectra[idx].tolist()

                message = ['data', metadata, spectra]
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
        get_data_sample() [or socket open() on socket creation?].

        """

        if 'data' == msg[0]:
            try:
                data = json.dumps(msg)
            except TypeError:
                logging.error('FOUND A NUMPY ARRAY!')
                logging.error(type(msg[3][0]))
                sys.exit()

        elif 'bank_config' == msg[0]:
            logging.debug(repr(msg))
            data = repr(msg)

        else:
            logging.debug(repr(msg))
            data = repr(msg)

        # the following line sends the data to the JS client
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)

    def on_close(self):

        if self.connections:
            self.connections.pop()

        else:
            ZMQWebSocket.requesting_data = False

        logging.info("Connections: {}".format(len(self.connections)))
