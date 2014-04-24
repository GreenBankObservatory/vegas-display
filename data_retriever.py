import threading
import sys

import numpy as np
import zmq

from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *

from read_file_data import *
from server_config import *

class VEGASReader():
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
                    t = threading.Thread(target=df.ParseFromString,
                                         args=(manager_response[1],))
                    t.start()
                    t.join()
                else:
                    df = DF()

                n_sig_states = len(set(df.sig_ref_state))
                n_cal_states = len(set(df.cal_state))
                n_subbands = len(set(df.subband))
                n_chans, n_samplers, n_states = df.data_dims

                # create a structure resembling the SAMPLER table from
                # the VEGAS FITS file
                sampler_dtype = [('BANK_A', np.str_, 8), ('PORT_A', int),
                                 ('BANK_B', np.str_, 8), ('PORT_B', int),
                                 ('SUBBAND', int), ('CRVAL1', float),
                                 ('CDELT1', float)]

                SAMPLER_TABLE = np.array(zip(df.bankA, df.portA,
                                             df.bankB, df.portB,
                                             df.subband, df.crval1,
                                             df.cdelt1), dtype=sampler_dtype)

                # calculate frequencies
                lo1, iffile_info = info_from_files(df.project_id, df.scan_number)

                backend, port, bank = 'VEGAS', 1, 'A'  # replace hard-coded
                sff_sb, sff_multi, sff_offset = iffile_info[(backend, port, bank)]


                arr = np.array(df.data)
                if DO_PARSE:
                    arr = arr.reshape(df.data_dims[::-1])

                    n_skip = (n_samplers/n_subbands)
                    if DEBUG:
                        print 'skip every ', n_skip
                        
                    if n_sig_states == 1:
                        # assumes no SIG switching

                        # average the cal-on/off pairs
                        # this reduces the second dimension by 1/2
                        # i.e. 2,14,1024 becomes 2,7,1024

                        arr = np.mean(arr, axis=0)

                        # get every other spectrum
                        less_arr = arr[::n_skip]
                        
                        subband = df.subband[::n_skip]

                        crval1 = [SAMPLER_TABLE[SAMPLER_TABLE['SUBBAND']==sb]['CRVAL1'][0] for sb in subband]
                        cdelt1 = [SAMPLER_TABLE[SAMPLER_TABLE['SUBBAND']==sb]['CDELT1'][0] for sb in subband]

                        all_sky_frequencies = []
                        for ii, spec in enumerate(less_arr):
                            ifval = np.array(range(1,df.number_channels+1))
                            ifval = crval1[ii] + cdelt1[ii] * (ifval - df.crpix1)
                            skyfreq = sff_sb * ifval + sff_multi * lo1 + sff_offset
                            print skyfreq/1e9
                            all_sky_frequencies.extend(skyfreq[::df.number_channels/NCHANS])

                        #spectrum = arr[::n_skip,:].ravel()
                        pdb.set_trace()

                        # rebin each of the spectra

                        all_rebinned_spectra = []
                        for xx in arr:
                            spectrum = arr[xx]
                            rebinned = spectrum.reshape((NCHANS, len(spectrum)/NCHANS)).mean(axis=1)
                            all_rebinned_spectra.extend(rebinned)
                        spectrum = np.array(zip(all_rebinned_spectra, all_sky_frequencies))
                    else:
                        # just show the first states
                        spectrum = arr[0,::n_skip,:].ravel()
                        
                    # !!! will not be needed
                    spectrum = spectrum / df.integration_time[0]
                else:
                    spectrum = arr
    
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

                (scan, project, spectrum, integration) = self.handle_response(response)

                # if something changed
                if scan != self.prev_scan or integration != self.prev_integration:
                    self.prev_scan = scan
                    self.prev_integration = integration
                    return ['ok', spectrum, project, scan, state, integration]
                else:  # if nothing changed
                    return ['same', spectrum, project, scan, state, integration]
            else:
                return ['error']

