#! /usr/bin/env python

import sys
import array
from time import strftime, sleep
import logging
import random
import math
import os
import logging
import argparse

from server_config import *
from read_file_data import *

import zmq
import numpy as np
import Gnuplot

from PBDataDescriptor_pb2 import *
from PBVegasData_pb2 import *
from request_pb2 import *
from DataStreamUtils import *

# configure the logger
log_level = {"err"  : logging.ERROR,
             "warn" : logging.WARNING,
             "info" : logging.INFO,
             "debug": logging.DEBUG}

def make_dummy_frequencies(n_subbands):
    frequencies = []
    for n in range(n_subbands):
        start = n * 1000
        sf = range(start, start + NCHANS)
        frequencies.extend(sf)
    
    return frequencies

def sky_frequencies(spectra, subbands, df):

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
        display_sky_frequencies.extend((skyfreq[::df.number_channels/NCHANS]/1e9).tolist())

    return display_sky_frequencies

def blank_plot(g):
    g('unset key')
    g.plot('[][0:1] 2')

def main(bank):
    mjr, mnr = "VEGAS", "Bank{}Mgr".format(bank)
    state_key = "{}.{}:P:state".format(mjr,mnr)
    data_key = "{}.{}:Data".format(mjr,mnr)
    context   = zmq.Context(1)

    # get URLs
    
    # directory request(device services) and publish(new interfaces) URLs
    _, directory_url, directory_event_url = get_directory_endpoints()

    # VEGAS BankA snapshot URLs
    vegas_snap_url,_,_ = get_service_endpoints(context, directory_url, mjr, mnr, SERV_SNAPSHOT) 

    logging.info('directory (request/services)        url: {}'.format(directory_url))
    logging.info('directory (publish/newinterfaces)   url: {}'.format(directory_event_url))
    logging.info('vegas snapshot                      url: {}'.format(vegas_snap_url))

    # connect sockets
    directory_socket = open_a_socket(context, directory_event_url, zmq.SUB)
    directory_socket.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    data_socket = open_a_socket(context, vegas_snap_url, zmq.REQ)

    logging.info('directory socket: {}'.format(directory_socket))
    logging.info('snap socket     : {}'.format(data_socket))

    # create poller to watch sockets
    poller = zmq.Poller()
    poller.register(directory_socket, zmq.POLLIN)
    poller.register(data_socket, zmq.POLLIN)

    request_pending = False
    gbank = Gnuplot.Gnuplot(persist=0)
    gbank.xlabel('GHz')
    gbank.ylabel('counts')
    gbank('set term png enhanced font '
          '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
          '9 size 600,200')
    gbank('set data style lines')
    gwindow = Gnuplot.Gnuplot(persist=0)
    gwindow.xlabel('GHz')
    gwindow.ylabel('counts')
    gwindow('set term png enhanced font '
            '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
            '9 size 600,200')
    gwindow('set data style lines')

    prevscan, prevint = None, None
    while True:
        value, request_pending = get_value(context, bank, poller, state_key,
                                           directory_socket, data_socket,
                                           request_pending, directory_url)
        if value:
            logging.debug('{} = {}'.format(state_key,value))

        gbank('set out "static/{}.png"'.format(bank))

        if ALWAYS_UPDATE: ready_for_value = True
        else: ready_for_value = (value == 'Running')

        if ready_for_value:
            value, request_pending = get_value(context, bank, poller, data_key,
                                               directory_socket, data_socket,
                                               request_pending, directory_url)
            if value:
                proj, scan, integration, spec = value
                logging.debug('{} {} {} {}'.format(proj, scan, integration, spec.shape))

                if (prevscan,prevint) != (scan,integration) or ALWAYS_UPDATE:
                    prevscan = scan
                    prevint = integration
                    if len(spec) == 1:
                        gbank('unset key')
                    else:
                        gbank('set key default')

                    gbank.title('Spec. {} '
                                  'Scan {} '
                                  'Int. {} {}'.format(bank, scan, 
                                                      integration,
                                                      strftime('  %Y-%m-%d %H:%M:%S')))
    
                    ds = []
                    for win,ss in enumerate(spec):
                        dd = Gnuplot.Data(ss, title='{}'.format(win))
                        ds.append(dd)
                    gbank.plot(*ds)

                    for window in range(8):
                        gwindow.title('Spec. {} Win. {} '
                                      'Scan {} '
                                      'Int. {} {}'.format(bank, window, scan, 
                                                          integration,
                                                          strftime('  %Y-%m-%d %H:%M:%S')))
                        gwindow('set out "static/{}{}.png"'.format(bank, window))
                        if window < len(spec):
                            gwindow('set key default')
                            gwindow.plot(spec[window])
                        else:
                            blank_plot(gwindow)
            else:
                gbank.title('Spec. {} {}'.format(bank, strftime('  %Y-%m-%d %H:%M:%S')))
                blank_plot(gbank)

        else:
            gbank.title('Spec. {} {}'.format(bank, strftime('  %Y-%m-%d %H:%M:%S')))
            blank_plot(gbank)
            for window in range(8):
                gwindow.title('Spectrometer {} '
                              'Window {} {}'.format(bank, window, strftime('  %Y-%m-%d %H:%M:%S')))
                gwindow('set out "static/{}{}.png"'.format(bank, window))
                blank_plot(gwindow)

        # pace the data requests    
        sleep(UPDATE_RATE)

def get_value(context, bank, poller, key, directory_socket,
              data_socket, request_pending, directory_url):
    # This is the REQ wrinkle: only send a request if the last
    # one was serviced. We might find ourselves back here if the
    # directory message was received instead of the data request,
    # in which case we must not make another request. In this
    # case, skip and drop into the poll to wait for the data.
    if not request_pending:
        data_socket.send(key)
        request_pending = True

    # this will block. May unblock if request is serviced, *or*
    # if directory service message is received.
    socks = dict(poller.poll())
    logging.debug('{} socks {}'.format(strftime('%Y/%m/%d %H:%M:%S'), socks))

    # handle directory service message
    if directory_socket in socks and socks[directory_socket] == zmq.POLLIN:
        key, payload = directory_socket.recv_multipart()
        handle_publisher(context, directory_url, bank, data_socket, payload)
        return None, None

    # handle data response
    if data_socket in socks and socks[data_socket] == zmq.POLLIN:
        data = handle_data(data_socket, key)

        if data:
            if key.endswith('Data'):
                value = data
            else: # state
                value = data.val_struct[0].val_string[0]
        else:
            value = None

        # indicate we can send a new request next time through loop.
        return value, False
    
def open_a_socket(context, url, service_type=zmq.REQ):
    socket = context.socket(service_type) # zmq.REQ || zmq.SUB
    socket.linger = 0 # do not wait for more data when closing
    socket.connect(url)
    return socket

def handle_publisher(context, directory_url, bank, data_socket, payload):
    # directory service, new interface. If it's ours,
    # need to reconnect.
    reqb = PBRequestService()
    reqb.ParseFromString(payload)

    # If we're here it's possibly because our device
    # restarted, or name server came back up, or some
    # other service registered with the directory
    # service. If the manager restarted the 'major',
    # 'minor' and 'interface' will mach ours, and the
    # URL will be different, so we need to
    # resubscribe. Check for the snapshot interface.
    # If not, we might respond to a message for the
    # wrong interface, in which case 'vegas_snap_url' will
    # be empty and the connection attempt below will
    # fail.
    logging.warning('{} {} {}'.format(reqb.major, reqb.minor, reqb.url))

    major, minor = "VEGAS", "Bank{}Mgr".format(bank)
    if (reqb.major == major and
        reqb.minor == minor and
        reqb.interface == SERV_SNAPSHOT):

        new_url = reqb.url[0]  # 0 for tcp, 1 for ipc, 2 for inproc

        if vegas_snap_url != new_url:
            restart_msg = "Manager restarted: %s.%s, %s, %s" % \
                          (reqb.major, reqb.minor, reqb.interface, new_url)
            logging.warning('{} {}'.format(datetime.now(), restart_msg))
            data_file = get_data_file(major, minor)

            vegas_snap_url = new_url

            if vegas_snap_url:
                logging.warning("new vegas_snap_url: {}".format(vegas_snap_url))
                data_socket.close()
                data_socket = open_a_socket(context, vegas_snap_url, zmq.REQ)
            else:
                logging.warning("Manager {}.{} subscription "
                                "URL is empty! exiting...".format(mjr, mnr))
                return
    

def handle_data(sock, key):
    rl = []
    rl = sock.recv_multipart()

    el = len(rl)

    if el == 1:  # Got an error
        if rl[0] == "E_NOKEY":
            logging.info("No key/value pair found: {}".format(key))
            return None
    elif el > 1:
        # first element is the key
        # the following elements are the values
        if not rl[0].endswith("Data"):
            df = PBDataField()
            df.ParseFromString(rl[1])
            return df
        else:
            df = pbVegasData()
            df.ParseFromString(rl[1])
            ff = array.array('f') # 'f' is typecode for C float
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
            n_pols = (n_samplers/n_subbands)
            logging.debug('polarization estimate: {}'.format(n_pols))
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
            # get every n_pols spectrum and subband
            less_spectra = arr[::n_pols]
            subbands = df.subband[::n_pols]
            
            try:
                sky_freqs = sky_frequencies(less_spectra, subbands, df)
            except:
                logging.debug('Frequency information unavailable.  '
                              'Substituting with dummy freq. data.')
                sky_freqs = make_dummy_frequencies(n_subbands)
            
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
                # N = 2 ^ (log2(raw_nchans) - log2(display_nchans))
                N = 2 ** (math.log(len(spectrum),2) - math.log(NCHANS,2))
                sampled = spectrum[(N/2):len(spectrum)-(N/2)+1:N]
                logging.debug('sampled spectrum length: {}'.format(len(sampled)))
                sampled_spectra.extend(sampled.tolist())
            
            spectrum = np.array(zip(sky_freqs, sampled_spectra))
            spectrum = spectrum.reshape((n_subbands,NCHANS,2)).tolist()
            
            # sort each spectrum by frequency
            for idx,s in enumerate(spectrum):
                spectrum[idx] = sorted(s)
            
            project = str(df.project_id)
            scan = int(df.scan_number)
            integration = int(df.integration)
            
            response = (project, scan, integration, np.array(spectrum))
            return response
    else:
        return None

if __name__ == '__main__':
    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("bank", help="port number to use on the server",
                        choices=['A','B','C','D','E','F','G','H',
                                 'a','b','c','d','e','f','g','h'],
                        type=str.upper)
    parser.add_argument("-v", help="verbosity output level", type=str,
                        choices=('err', 'warn', 'info', 'debug'), default='info')
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=log_level[args.v])
    main(args.bank)
