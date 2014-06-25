import random
import threading
import sys
import array
from pprint import pprint

import numpy as np
import zmq

from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

from read_file_data import *
from server_config import *

class VEGASReader():
    def __del__(self,):
        for b in self.banks:
            self.request_url[b].close()
            self.context[b].close()
                
    def __init__(self,):

        if DEBUG: print 'Initializing VEGASReader'

        self.prev_scan = None
        self.prev_integration = None


        self.banks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        self.active_banks = []

        self.directory_url = get_directory_endpoints("request")

        self.context = {}
        self.request_url = {}
        self.device_url = {}
        self.major_key = {}
        self.minor_key = {}

        for b in self.banks:

            self.context[b] = zmq.Context()

            if LIVE:
                self.major_key[b] = "VEGAS"
                self.minor_key[b] = "Bank{0}Mgr".format(b)
            else:
                self.major_key[b] = "VegasTest"
                self.minor_key[b] = self.major_key[b] + b

            self.device_url[b] = get_service_endpoints(self.context[b], self.directory_url,
                                                       self.major_key[b], self.minor_key[b], 1)
            
            self.request_url[b] = self.context[b].socket(zmq.REQ)

            if DEBUG: print 'device and request urls', self.device_url, self.request_url
            if self.request_url[b] and ("nrao.edu" in self.device_url[b]):
                self.request_url[b].connect(self.device_url[b])
                self.active_banks.append(b)

        if DEBUG: print 'Initialized VEGASReader', self.device_url, self.request_url

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
                if DEBUG:  print df.name, '=', response
                return response

            else:
                # key is 'Data'
                if DO_PARSE:
                    df = pbVegasData()
                    df.ParseFromString(values)
                    ff = array.array('f')  # 'f' is typecode for C float
                    ff.fromstring(df.data_blob)
                    #t = threading.Thread(target=ff.fromstring, args=(df.data_blob,))
                    #t.start()
                    #t.join()
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

                    if DEBUG: print 'polarization estimate:', n_skip_pols

                    if n_sig_states == 1:
                        # assumes no SIG switching

                        # average the cal-on/off pairs
                        # this reduces the state dimension by 1/2
                        # i.e. 2,14,1024 becomes 1,14,1024 or 14,1024
                        arr = np.mean(full_res_spectra, axis=0)
                    else:
                        if DEBUG: print 'SIG SWITCHING'
                        pass

                        # get just the first spectrum
                        arr = full_res_spectra[0]

                    # get every n_skip_pols spectrum and subband
                    less_spectra = arr[::n_skip_pols]
                    subbands = df.subband[::n_skip_pols]

                    sky_frequencies = []
                    if LIVE:
                        sky_frequencies = self.sky_frequencies(less_spectra, subbands, df)
                    else:
                        for n in range(n_subbands):
                            start = random.randint(1,5)*1000
                            sf = range(start,start+NCHANS)
                            sky_frequencies.extend(sf)

                    # rebin each of the spectra
                    rebinned_spectra = []
                    for xx in less_spectra:
                        spectrum = xx
                        if DEBUG: spectrum = spectrum * random.randint(1,10)
                        # rebin to NCHANS length
                        rebinned = spectrum.reshape((NCHANS, len(spectrum)/NCHANS)).mean(axis=1)
                        rebinned_spectra.extend(rebinned.tolist())


                    spectrum = np.array(zip(sky_frequencies, rebinned_spectra))
                    spectrum = spectrum.reshape((n_subbands,NCHANS,2)).tolist()

                    # sort each spectrum by frequency
                    for idx,s in enumerate(spectrum):
                        spectrum[idx] = sorted(s)
                        
                    # !!! will not be needed
                    # spectrum = spectrum / df.integration_time[0]
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

    def get_state(self, bank):
        """
        """
        # a device url should be of the form tcp://machine.nrao.edu:port
        #  for example, tcp://colossus.gb.nrao.edu:43565
        # if a device is not present the url is 'NOT FOUND!'
        if "nrao.edu" in self.device_url[bank]:
            stateKey = "%s.%s:P:state" % (self.major_key[bank], self.minor_key[bank])
            self.request_url[bank].send(str(stateKey))
            response = self.request_url[bank].recv_multipart()
            state = self.handle_response(response)
            return state
        else:
            return 'Error'

    def get_data_sample(self, bank):
        """Connect (i.e. subscribe) to a data publisher.

        Arguments:
        bank -- the name of the bank (e.g. 'A')

        """

        if DEBUG: print 'getting state of bank', bank
        state = self.get_state(bank)

        if DEBUG: print 'bank {0} state {1}'.format(bank, state)

        if "Running" == state or "Committed" == state:
            try:
                dataKey = "%s.%s:Data" % (self.major_key[bank], self.minor_key[bank])
                self.request_url[bank].send(str(dataKey))
                response = self.request_url[bank].recv_multipart()
                (project, scan, integration, spectrum) = self.handle_response(response)
            except e:
                if DEBUG: print 'ERROR for',bank
                if DEBUG: print e
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
            return ['error']

