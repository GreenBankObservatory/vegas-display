import random
import threading
import sys
import traceback # for debugging
import array
from pprint import pformat
import re
import logging
import math

import numpy as np
import zmq
from blessings import Terminal

from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *
from DataStreamUtils import *

from read_file_data import *
from server_config import *

def open_a_socket(context, url, service_type=zmq.REQ):
    socket = context.socket(service_type) # zmq.REQ || zmq.SUB
    socket.linger = 0 # do not wait for more data when closing
    socket.connect(url)
    return socket

class VEGASReader():
    def __del__(self,):
        for b in self.banks:
            self.snapshot_socket[b].close()
        self.ctx.close()
                
    def __init__(self,):

        logging.debug('Initializing VEGASReader')

        self.term = Terminal()

        self.prev_scan = None
        self.prev_integration = None


        self.banks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        self.active_banks = []

        self.snapshot_socket = {}
        self.manager_url = {}
        self.major_key = {}
        self.minor_key = {}

        self.ctx = zmq.Context()

        # Connect to the directory service and watch it for new interface
        # messages that can occur with restarts to any of the managers, as well
        # as new devices registering with the directory
        _, self.directory_request_url, directory_publisher_url = get_directory_endpoints()
        self.directory_socket = open_a_socket(self.ctx, directory_publisher_url, zmq.SUB)
        self.directory_socket.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")
#        self.directory_socket.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:SERVER_DOWN")
#        self.directory_socket.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:SERVER_UP")

        # a ZMQ poller will repeatedly check all registered socket connections
        # we use it to check both the directory and each of the VEGAS banks
        self.poller = zmq.Poller()
        self.poller.register(self.directory_socket, zmq.POLLIN)

        # this flag is to make sure we don't make extra requests to a VEGAS
        # bank without reading the last response first
        self.request_pending = False

        # look for banks that are active
        self.find_active_banks()

        logging.info('manager urls:')
        logging.info(pformat(self.manager_url))
        logging.info('snapshot sockets:')
        logging.info(pformat(self.snapshot_socket))
        logging.info('active banks: {}'.format(self.active_banks))
        logging.info('Initialized VEGASReader')

    def find_active_banks(self):
        # this is where we collect urls and open snapshot sockets for each of
        # the VEGAS banks.  If a bank is not listed in the directory with a
        # valid looking URL, then it is not considered active.
        for bank in self.banks:

            self.major_key[bank] = "VEGAS"
            self.minor_key[bank] = "Bank{0}Mgr".format(bank)

            snapshot_interface = 1
            self.manager_url[bank] = get_service_endpoints(self.ctx, self.directory_request_url,
                                                           self.major_key[bank], self.minor_key[bank],
                                                           snapshot_interface)[0]

            if "//" in self.manager_url[bank]:
                self.snapshot_socket[bank] = open_a_socket(self.ctx, self.manager_url[bank])
                self.poller.register(self.snapshot_socket[bank], zmq.POLLIN)
                self.active_banks.append(bank)

    def sky_frequencies(self, spectra, subbands, df):

        # ----------------------  calculate frequencies

        # create a structure resembling the SAMPLER table from
        #   the VEGAS FITS file
        sampler_dtype = [('BANK_A', np.str_, 8), ('PORT_A', int),
                         ('BANK_B', np.str_, 8), ('PORT_B', int),
                         ('SUBBAND', int), ('CRVAL1', float),
                         ('CDELT1', float)]
        SAMPLER_TABLE = np.array(zip(df.bankA, df.portA,
                                     df.bankB, df.portB,
                                     df.subband, df.crval1,
                                     df.cdelt1), dtype=sampler_dtype)

        lo1, iffile_info = info_from_files(df.project_id, df.scan_number)

        backend, port, bank = 'VEGAS', 1, SAMPLER_TABLE['BANK_A'][0]
        sff_sb, sff_multi, sff_offset = iffile_info[(backend, port, bank)]

        crval1 = []
        cdelt1 = []
        for sb in subbands:
            mask = SAMPLER_TABLE['SUBBAND']==sb
            crval1.append(SAMPLER_TABLE[mask]['CRVAL1'][0])
            cdelt1.append(SAMPLER_TABLE[mask]['CDELT1'][0])

        display_sky_frequencies = []
        for ii, spec in enumerate(spectra):
            ifval = np.array(range(1,df.number_channels+1))
            # Below I use df.number_channels/2 instead of df.crpix1 because crpix1 
            #  is currently holding the incorrect value of 0.
            # That is a bug in the protobuf Data key sent in the stream from
            #  the manager.
            ifval = crval1[ii] + cdelt1[ii] * (ifval - df.number_channels/2)
            skyfreq = sff_sb * ifval + sff_multi * lo1 + sff_offset
            # only return NCHANS numbers of frequencies for each subband
            display_sky_frequencies.extend(skyfreq[::df.number_channels/NCHANS].tolist())

        return display_sky_frequencies

    def handle_response(self, manager_response):

        if not manager_response:
            return None
            
        response_length = len(manager_response)

        if response_length < 1:
            logging.debug('NO RESPONSE')
            return None

        if response_length == 1:
            # Got an error
            logging.error("From VEGAS Manager: {}".format(manager_response[0]))
            return None

        elif response_length > 1:
            # first element is the key
            # the following elements are the values
            key = manager_response[0]
            values = manager_response[1]

            if not key.endswith("Data"):
                df = PBDataField()
                df.ParseFromString(values)
                if key.endswith("state"):
                    response = str(df.val_struct[0].val_string[0])
                logging.debug('key = {t.bold}{t.green}{resp}{t.normal}'.format(resp=response, t=self.term))
                return response

            else:
                # key is 'Data'
                df = pbVegasData()
                df.ParseFromString(values)
                ff = array.array('f')  # 'f' is typecode for C float
                ff.fromstring(df.data_blob)
                
                n_sig_states = len(set(df.sig_ref_state))
                n_cal_states = len(set(df.cal_state))
                n_subbands = len(set(df.subband))
                n_chans, n_samplers, n_states = df.data_dims

                full_res_spectra = np.array(ff)
                logging.debug('full_res_spectra {}'.format(full_res_spectra[:10]))

                full_res_spectra = full_res_spectra.reshape(df.data_dims[::-1])

                # estimate the number of polarizations used to grab the first
                # of each subband
                n_skip_pols = (n_samplers/n_subbands)

                logging.debug('polarization estimate: {}'.format(n_skip_pols))

                if n_sig_states == 1:
                    # assumes no SIG switching

                    # average the cal-on/off pairs
                    # this reduces the state dimension by 1/2
                    # i.e. 2,14,1024 becomes 1,14,1024 or 14,1024
                    arr = np.mean(full_res_spectra, axis=0)
                else:
                    logging.debug('SIG SWITCHING')
                    pass

                    # get just the first spectrum
                    arr = full_res_spectra[0]

                # get every n_skip_pols spectrum and subband
                less_spectra = arr[::n_skip_pols]
                subbands = df.subband[::n_skip_pols]

                sky_frequencies = []
                try:
                    sky_frequencies = self.sky_frequencies(less_spectra, subbands, df)
                except:
                    logging.warning('Frequency information unavailable.  Substituting with dummy freq. data.')
                    for n in range(n_subbands):
                        start = random.randint(1,5)*1000
                        sf = range(start,start+NCHANS)
                        sky_frequencies.extend(sf)

                # rebin each of the spectra
                sampled_spectra = []
                for xx in less_spectra:
                    spectrum = xx

                    # interpolate over the center channel to remove the VEGAS spike
                    centerchan = int(len(spectrum)/2)
                    spectrum[centerchan] = (spectrum[(centerchan)-1] + spectrum[(centerchan)+1])/2.

                    # rebin to NCHANS length
                    logging.debug('raw spectrum length: {}'.format(len(spectrum)))

                    # sample every N channels of the raw spectrum, where
                    #  N = 2 ^ (log2(raw_nchans) - log2(display_nchans))
                    N = 2 ** (math.log(len(spectrum),2) - math.log(NCHANS,2))
                    sampled = spectrum[(N/2):len(spectrum)-(N/2)+1:N]
                    logging.debug('sampled spectrum length: {}'.format(len(sampled)))
                    sampled_spectra.extend(sampled.tolist())


                spectrum = np.array(zip(sky_frequencies, sampled_spectra))
                spectrum = spectrum.reshape((n_subbands,NCHANS,2)).tolist()

                # sort each spectrum by frequency
                for idx,s in enumerate(spectrum):
                    spectrum[idx] = sorted(s)

                project = str(df.project_id)
                scan = int(df.scan_number)
                integration = int(df.integration)

                # make sure we have lists
                for idx,s in enumerate(spectrum):
                    for widx,w in enumerate(s):
                        if type(w) != type([]) and hasattr(w, "tolist"):
                            spectrum[idx][widx] = w.tolist()


                for idx,s in enumerate(spectrum):
                    if type(s) != type([]) and hasattr(s, "tolist"):
                        spectrum[idx] = s.tolist()

                if type(spectrum) != type([]):
                    spectrum = spectrum.tolist()
                    
                response = (project, scan, integration, spectrum)

                return response

    def parse_key(self, mykey):
        match_obj = re.match(r'(VEGAS)\.(Bank.Mgr):.*', mykey, re.I)
        # match object is None if there wasn't a match
        if match_obj:
            (major, minor) = match_obj.groups()
            bank_match_obj = re.match(r'Bank(.)Mgr', minor, re.I)
            if bank_match_obj:
                bank = bank_match_obj.groups()[0]
                return (major, minor, bank)
            else:
                logging.error('can not identify bank name from key {}'.format(mykey))
                return None
        else:
            logging.error('unexpected key value {}'.format(mykey))
            return None

    def check_response(self, socket, mykey):

        key_parts = self.parse_key(mykey)
        if not key_parts:
            return None
        else:
            (major, minor, bank) = key_parts

        socks = dict(self.poller.poll(100)) # timeout after 100ms

        if ((self.directory_socket in socks) and (socks[self.directory_socket] == zmq.POLLIN)):
            logging.debug('WE received a NEW_INTERFACE message.')
            (received_key, payload) = self.directory_socket.recv_multipart(zmq.NOBLOCK)

            if received_key == "YgorDirectory:NEW_INTERFACE":
                # new interface announced by directory
                reqb = PBRequestService()
                reqb.ParseFromString(payload)

                # if we're here it's possilbly because our device
                # restarted, or the name server came back up, or
                # some other service registered with the directory
                # service.  If the manager restart the 'major',
                # 'minor' and 'interface' will match and the URL will
                # be different, so we need to resubscribe.
                logging.info("New Interface: "
                             "{0} {1} interface {2}".format(reqb.major, reqb.minor,
                                                            reqb.interface))
                snapshot_index = 1 # snapshot
                logging.debug("{} {} =? {} {}".format(reqb.major, reqb.interface,
                                                      major, snapshot_index))

                if (reqb.major, reqb.interface) == (major, snapshot_index):
                    new_url = reqb.url[0]
                    
                    bank_match_obj = re.match(r'Bank(.)Mgr', reqb.minor, re.I)
                    if bank_match_obj:
                        reqb_bank = bank_match_obj.groups()[0]      
                        logging.debug('Bank restarted: {}'.format(reqb_bank))
                    else:
                        logging.error('ERROR: Could not determine '
                                      'bank from minor key: {}'.format(reqb.minor))
                        return None

                    logging.debug('URLS: {0} (old)\n'
                                 '      {1} (new)'.format(self.manager_url[reqb_bank], new_url))

                    logging.info('Manager restarted: '
                                 '{0}.{1}, interface {2}, {3}'.format(reqb.major, reqb.minor,
                                                                      reqb.interface, new_url))

                    self.manager_url[reqb_bank] = new_url
                    snapshot_socket = self.snapshot_socket[reqb_bank]

                    if new_url:
                        logging.info('New snapshot url for bank {0}: {1}'.format(reqb_bank, new_url))

                        # unregister and close
                        if snapshot_socket in self.poller.sockets:
                            self.poller.unregister(snapshot_socket)
                        if not snapshot_socket.closed:
                            snapshot_socket.close()

                        # create socket, connect and register poller with new url
                        self.snapshot_socket[reqb_bank] = open_a_socket(self.ctx, new_url)
                        self.poller.register(self.snapshot_socket[reqb_bank], zmq.POLLIN)
                           
            return None

        if ((socket in socks) and (socks[socket] == zmq.POLLIN)):
            response = socket.recv_multipart(zmq.NOBLOCK)
            logging.debug('Manager responded for: {}'.format(mykey))
            self.request_pending = False
            return response
        else:
            logging.debug('ERROR: poll() timed out or did not have expected url')
            return None

    def send_request(self, socket, mykey):
        logging.debug('Requesting from manager: {}'.format(mykey))
        if not self.request_pending:
            try:
                socket.send(mykey, zmq.NOBLOCK)
                self.request_pending = True
            except zmq.ZMQError as err:
                if err.errno == zmq.EAGAIN:
                    logging.debug('Nothing to receive.')
                else:
                    traceback.print_exc();
                self.request_pending = False
        else:
            logging.debug('Requesting pending: {}'.format(mykey))
        
    def get_state(self, bank):
        """
        """
        # a device url should be of the form tcp://machine.nrao.edu:port
        #  for example, tcp://colossus.gb.nrao.edu:43565
        # if a device is not present the url is 'NOT FOUND!'
        if "nrao.edu" in self.manager_url[bank]:
            stateKey = "%s.%s:P:state" % (self.major_key[bank], self.minor_key[bank])
            self.send_request(self.snapshot_socket[bank], stateKey)
            response = self.check_response(self.snapshot_socket[bank], stateKey)
            return self.handle_response(response)
        else:
            return 'Error'

    def get_data_sample(self, bank):
        """Connect (i.e. subscribe) to a data publisher.

        Arguments:
        bank -- the name of the bank (e.g. 'A')

        """

        state = self.get_state(bank)

        if True:#"Running" == state:
            try:
                socket = self.snapshot_socket[bank]
                dataKey = "{}.{}:Data".format(self.major_key[bank], self.minor_key[bank])

                if not self.request_pending:
                    self.send_request(socket, dataKey)

                response = self.check_response(socket, dataKey)

                if response:
                    (project, scan, integration, spectrum) = self.handle_response(response)

                    # if something changed, send 'ok'
                    if scan != self.prev_scan or integration != self.prev_integration:
                        self.prev_scan = scan
                        self.prev_integration = integration
                        return ['ok', spectrum, project, scan, state, integration]

                    # if nothing changed, send 'same'
                    else:
                        return ['same', spectrum, project, scan, state, integration]
                else:
                    return ['idle']
                    
            except:
                return ['error']

        else:
            return ['idle']

