import random
import threading
import sys
import array
from pprint import pprint
import re

import numpy as np
import zmq

from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

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

        if DEBUG: print 'Initializing VEGASReader'

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

        # print out some debug info to see what we have
        if DEBUG:
            print 'manager urls:'
            pprint(self.manager_url)
            print 'snapshot sockets:'
            pprint(self.snapshot_socket)
            print 'active banks:', self.active_banks
            print 'Initialized VEGASReader'

    def find_active_banks(self):
        # this is where we collect urls and open snapshot sockets for each of
        # the VEGAS banks.  If a bank is not listed in the directory with a
        # valid looking URL, then it is not considered active.
        for bank in self.banks:

            if LIVE:
                self.major_key[bank] = "VEGAS"
                self.minor_key[bank] = "Bank{0}Mgr".format(bank)
            else:
                self.major_key[bank] = "VegasTest"
                self.minor_key[bank] = self.major_key[bank] + bank

            snapshot_interface = 1
            self.manager_url[bank] = get_service_endpoints(self.ctx, self.directory_request_url,
                                                           self.major_key[bank], self.minor_key[bank],
                                                           snapshot_interface)

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
            ifval = crval1[ii] + cdelt1[ii] * (ifval - df.crpix1)
            skyfreq = sff_sb * ifval + sff_multi * lo1 + sff_offset
            # only return NCHANS numbers of frequencies for each subband
            display_sky_frequencies.extend(skyfreq[::df.number_channels/NCHANS].tolist())

        return display_sky_frequencies

    def handle_response(self, manager_response):
        response_length = len(manager_response)

        if response_length < 1:
            if DEBUG: print 'NO RESPONSE'
            return None

        if response_length == 1:
            # Got an error
            if DEBUG: print "Error message from VEGAS Manager:", manager_response[0]
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
                if DEBUG:  print key, '=', response
                return response

            else:
                # key is 'Data'
                if DO_PARSE:
                    df = pbVegasData()
                    df.ParseFromString(values)
                    ff = array.array('f')  # 'f' is typecode for C float
                    ff.fromstring(df.data_blob)
                else:
                    df = DF()
                    ff = df.data
                
                n_sig_states = len(set(df.sig_ref_state))
                n_cal_states = len(set(df.cal_state))
                n_subbands = len(set(df.subband))
                n_chans, n_samplers, n_states = df.data_dims

                full_res_spectra = np.array(ff)
                #if DEBUG: print 'full_res_spectra',full_res_spectra[:10]

                if DO_PARSE:
                    full_res_spectra = full_res_spectra.reshape(df.data_dims[::-1])

                    # estimate the number of polarizations used to grab the first
                    # of each subband
                    n_skip_pols = (n_samplers/n_subbands)

                    #if DEBUG: print 'polarization estimate:', n_skip_pols

                    if n_sig_states == 1:
                        # assumes no SIG switching

                        # average the cal-on/off pairs
                        # this reduces the state dimension by 1/2
                        # i.e. 2,14,1024 becomes 1,14,1024 or 14,1024
                        arr = np.mean(full_res_spectra, axis=0)
                    else:
                        #if DEBUG: print 'SIG SWITCHING'
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
                        if DEBUG: print 'WARNING: frequency information unavailable'
                        for n in range(n_subbands):
                            start = random.randint(1,5)*1000
                            sf = range(start,start+NCHANS)
                            sky_frequencies.extend(sf)

                    # rebin each of the spectra
                    rebinned_spectra = []
                    for xx in less_spectra:
                        spectrum = xx

                        # interpolate over the center channel to remove the VEGAS spike
                        centerchan = int(len(spectrum)/2)
                        spectrum[centerchan] = (spectrum[(centerchan)-1] + spectrum[(centerchan)+1])/2.

                        if DEBUG:
                            spectrum = spectrum * random.randint(1,10)

                        # rebin to NCHANS length
                        rebinned = spectrum.reshape((NCHANS, len(spectrum)/NCHANS)).mean(axis=1)
                        rebinned_spectra.extend(rebinned.tolist())


                    spectrum = np.array(zip(sky_frequencies, rebinned_spectra))
                    spectrum = spectrum.reshape((n_subbands,NCHANS,2)).tolist()

                    # sort each spectrum by frequency
                    for idx,s in enumerate(spectrum):
                        spectrum[idx] = sorted(s)

                else:
                    spectrum = arr
    
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
                if type(response[3]) == type(np.zeros(1)):
                    print '',

                return response

    def check_response(self, socket, mykey):

        match_obj = re.match(r'(VEGAS)\.(Bank.Mgr):.*', mykey, re.I)
        # match object is None if there wasn't a match
        if match_obj:
            (major, minor) = match_obj.groups()
            bank_match_obj = re.match(r'Bank(.)Mgr', minor, re.I)
            if bank_match_obj:
                bank = bank_match_obj.groups()[0]
            else:
                print 'ERROR: can not identify bank name from key', mykey
                return None
        else:
            print 'ERROR: unexpected key value', mykey
            return None

        socks = dict(self.poller.poll())

        if ((self.directory_socket in socks) and (socks[self.directory_socket] == zmq.POLLIN)):
            print 'WE received a NEW_INTERFACE message!!'
            (received_key, payload) = self.directory_socket.recv_multipart()

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
                if DEBUG:
                    print("NEW INTERFACE: "
                          "{0} {1} interface {2}".format(reqb.major, reqb.minor,
                                                         reqb.interface))
                snapshot_index = 1 # snapshot
                if (reqb.major, reqb.minor, reqb.interface) == (major, minor, snapshot_index):
                   new_url == reqb.url[0]

                   if self.manager_url[bank] != new_url:
                       restart_msg = ('Manager restarted: '
                                      '{0}.{1}, {2}, {3}'.format(reqb.major, reqb.minor,
                                                                 interface, new_url))

                       self.manager_url[bank] = new_url
                       snapshot_socket = self.snapshot_socket[bank]

                       if new_url:
                           print 'New snapshot url for bank {0}: {1}'.format(bank, new_url)

                           # unregister and close
                           if snapshot_socket in self.poller.sockets:
                               self.poller.unregister(snapshot_socket)
                           if not snapshot_socket.closed:
                               snapshot_socket.close()

                           # create socket, connect and register poller with new url
                           snapshot_socket = open_a_socket(self.ctx, new_url)
                           self.poller.register(snapshot_socket, zmq.POLLIN)
                           
            return None

        if ((socket in socks) and (socks[socket] == zmq.POLLIN)):
            response = socket.recv_multipart()
            if DEBUG: print 'Manager responded for: {0}'.format(mykey)
            self.request_pending = False
            return response
        else:
            print 'ERROR: poll() did not have expected url'
            return None

    def send_request(self, socket, key):
        if DEBUG: print 'Requesting from manager: {0}'.format(key)
        socket.send(key)
        self.request_pending = True
        
    def get_state(self, bank):
        """
        """
        # a device url should be of the form tcp://machine.nrao.edu:port
        #  for example, tcp://colossus.gb.nrao.edu:43565
        # if a device is not present the url is 'NOT FOUND!'
        if "nrao.edu" in self.manager_url[bank]:
            stateKey = "%s.%s:P:state" % (self.major_key[bank], self.minor_key[bank])
            self.snapshot_socket[bank].send(str(stateKey))
            response = self.snapshot_socket[bank].recv_multipart()
            state = self.handle_response(response)
            return state
        else:
            return 'Error'

    def get_data_sample(self, bank):
        """Connect (i.e. subscribe) to a data publisher.

        Arguments:
        bank -- the name of the bank (e.g. 'A')

        """

        state = self.get_state(bank)

        if "Running" == state:
            try:
                socket = self.snapshot_socket[bank]
                dataKey = "{0}.{1}:Data".format(self.major_key[bank], self.minor_key[bank])

                if not self.request_pending:
                    self.send_request(socket, dataKey)

                response = self.check_response(socket, dataKey)

                if response:
                    (project, scan, integration, spectrum) = self.handle_response(response)
            except:
                if DEBUG: print 'ERROR for', bank, sys.exc_info()[0]
                return ['error']

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

