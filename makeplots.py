from server_config import *

import zmq
from zmq.eventloop import zmqstream

from time import strftime, sleep
import threading
import numpy as np
import sys
import json
import logging
import pylab as plt
from vegas_reader import VEGASReader

plt.rc('font', size='8')
plt.rc('xtick', labelsize='small')
plt.rc('lines', linewidth='.5', antialiased=True)
plt.rc('figure', figsize=(6,2))

class Plots():

    connections = []
    data = None
    plots_thread = None
    requesting_data = True
    vegasReader = None

    def query_vegas_managers(self,):
        """Start up the server that reads spectra from the VEGAS manger

        This server reads from the VEGAS manager, as long as there is
        at least one browser connection, and serves it up to
        the display clients.

        """

        logging.debug('querying vegas managers')
        Plots.vegasReader = VEGASReader()

        # continually request data from the VEGAS managers,
        # so long as there is at least one browser connection
        while self.requesting_data:

            all_banks_spectra, metadata = {}, {}
            have_metadata = False

            # request data for each of the banks (A-H)
            for bank in self.vegasReader.banks:

                if bank not in self.vegasReader.active_banks:
                    logging.debug('Bank {} is not active.  '
                                  'Sending empty list to client'.format(bank))
                    spectrum = []

                else:
                    try:
                        # collect some data for the bank
                        response = self.vegasReader.get_data_sample(bank)
                        # structure of response is:
                        #  result_state (e.g. 'ok' 'same' 'error)
                        #  (spectrum, project, scan, integration)
                    except:
                        logging.debug('ERROR getting data sample {}'.format(sys.exc_info()))
                        response = ['error']

                    if response[0] == 'error' or response[0] == 'idle' or response[0] == 'noresponse':
                        logging.debug('{}: recording empty list for {}'.format(response[0], bank))
                        spectrum = []

                    else:
                        spectrum = response[1]

                        # get metadata from the first bank
                        #  the metadata should be the same for all banks
                        if not have_metadata:
                            metadata = response[2]
                            if response[0] == 'same':
                                print 'same, not updating'
                                metadata['update'] = 0
                            else:
                                metadata['update'] = 1

                            if ALWAYS_UPDATE: metadata['update'] = 1
                            have_metadata = True

                all_banks_spectra[bank] = spectrum#np.array(zip(np.array(range(512)),np.random.random(512))).reshape((1,512,2)).tolist()

            # by setting self.data we allow on_message to
            #  write a message back to the client
            Plots.data = [metadata, all_banks_spectra]

            print(strftime("%H:%M:%S"))

    def plot_window(self, bank, win, vals):
        windowfig = plt.figure(2)
        windowfig.subplots_adjust(bottom=0.15, top=0.85)
        ax_win = windowfig.add_subplot(1,1,1)
        n_windows = len(vals)
        if win > n_windows-1:
            ax_win.plot(None)
        else:
            dta = vals[win]
            ax_win.plot(dta[:,0]/1e9, dta[:,1])

        ax_win.set_title("Spec. " + bank +
                         " Win. " + str(win) + 
                         " " + strftime("%Y/%m/%d %H:%M:%S"))
        ax_win.set_ylabel("counts")
        ax_win.set_xlabel("GHz")
        windowfig.savefig('static/{0}{1}.png'.format(bank,win))
        windowfig.clf()

    def plot_banks(self, specs):
        for bank in specs:
            bankfig = plt.figure(1)
            bankfig.subplots_adjust(bottom=0.15, top=0.85)
            vals = np.array(specs[bank])
            ax_bank = bankfig.add_subplot(1,1,1)
            n_windows = len(vals)
            for win in range(8):
                self.plot_window(bank, win, vals)
                if win > n_windows-1:
                    ax_bank.plot(None)
                else:
                    dta = vals[win]
                    ax_bank.plot(dta[:,0]/1e9, dta[:,1])

            ax_bank.set_title("Spectrometer " + bank + " " + 
                              strftime("%Y/%m/%d %H:%M:%S"))
            ax_bank.set_ylabel("counts")
            ax_bank.set_xlabel("GHz")
            bankfig.savefig('static/{0}.png'.format(bank))
            bankfig.clf()


    def make(self):
        """
        This method is called when the JS creates a WebSocket object.

        """
        # Start service that reads spectra from manager
        logging.info('starting plots thread')
        Plots.plots_thread = threading.Thread(target=self.query_vegas_managers)
        self.plots_thread.setDaemon(True)
        self.plots_thread.start()
        # give it a second to get started before looking for data
        sleep(1)

        while True:
            if hasattr(Plots, 'data') and Plots.data:
                metadata, spectra = self.data
                message = {
                    'header': 'data',
                    'body' : {'metadata' : metadata, 'spectra' : spectra}
                }
                print 'message', message['header'],  message['body']['metadata'],strftime("%Y/%m/%d %H:%M:%S")

                if message['body']:
                    specs = message['body']['spectra']
                    self.plot_banks(specs)
                    print "Made plots",strftime("%Y/%m/%d %H:%M:%S")

                Plots.data = None
                sleep(2)

    def on_close(self):
        self.connections.pop()

        if self.connections:
            Plots.requesting_data = False
            self.plots_thread.join()

        logging.info("Connections: {}".format(len(self.connections)))
