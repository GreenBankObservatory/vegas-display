import logging
from time import strftime, sleep
from datetime import datetime
import math
import array
import os

import numpy as np
import zmq

from gbtzmq.PBDataDescriptor_pb2 import PBDataField
from gbtzmq.PBVegasData_pb2 import pbVegasData
from gbtzmq.request_pb2 import PBRequestService
import gbtzmq.DataStreamUtils as dsu

import server_config as cfg
import read_file_data as filedata
import Gnuplot

LCLDIR = os.path.dirname(os.path.abspath(__file__))


def _get_tcp_url(urls):
    for u in urls:
        if "tcp" in u:
            return u
    return ""


def _make_dummy_frequencies(nsigs, n_subbands, npols):
    frequencies = []
    for _ in range(nsigs):
        for n in range(n_subbands):
            start = n * 1000
            sf = range(start, start + cfg.NCHANS)
            for _x in range(npols):
                frequencies.extend(sf)

    return frequencies


def _sampler_table(df):
    # create a structure resembling the SAMPLER table from
    #   the VEGAS FITS file
    sampler_dtype = [('BANK_A', np.str_, 8), ('PORT_A', int),
                     ('BANK_B', np.str_, 8), ('PORT_B', int),
                     ('SUBBAND', int), ('CRVAL1', float),
                     ('CDELT1', float)]
    sampler_table = np.array(zip(df.bankA, df.portA,
                                 df.bankB, df.portB,
                                 df.subband, df.crval1,
                                 df.cdelt1), dtype=sampler_dtype)
    return sampler_table


def _sky_frequencies(spectra, df):

    # The spectra array dimensions are now:
    #   sigref, windows, polarizations, channels
    nsig, nwin, npol, nchan = spectra.shape

    # ----------------------  calculate frequencies

    lo1, offset, iffile_info = filedata.info_from_files(df.project_id, df.scan_number)

    # NB 'BANK_A' is a column name that could hold ANY bank value
    # and not necessarily 'A'
    # The port number is (I think) a unique identifier for polarization
    #   but it shouldn't matter because frequencies should be the same
    #   for both polarizations.  So, I just grab the first.  port=1.

    sampler_table = _sampler_table(df)
    port, bank = 1, sampler_table['BANK_A'][0]
    _, sff_sb, sff_multi, sff_offset = iffile_info[(port, bank)]

    # The CRVAL1 and CDELT1 value differ with subband, so collect
    #   all of them for later reference to determine frequencies.
    crval1 = []
    cdelt1 = []
    for sb in df.subband:
        mask = sampler_table['SUBBAND'] == sb
        crval1.append(sampler_table[mask]['CRVAL1'][0])
        cdelt1.append(sampler_table[mask]['CDELT1'][0])

    display_sky_frequencies = []
    for count in range(nwin * npol):
        ifval = np.array(range(1, df.number_channels+1))
        # Below I use df.number_channels/2 instead of df.crpix1 because crpix1
        #  is currently holding the incorrect value of 0.
        # That is a bug in the protobuf Data key sent in the stream from
        #  the manager.
        ifval = crval1[count] + cdelt1[count] * (ifval - df.number_channels/2)
        skyfreq = sff_sb * ifval + sff_multi * lo1 + sff_offset

        # only return NCHANS numbers of frequencies for each subband
        reduced_skyfreqs = (skyfreq[::df.number_channels/cfg.NCHANS]/1e9).tolist()
        display_sky_frequencies.extend(reduced_skyfreqs + offset[0]/1e9)  # 0 represents the frequency signal

    if nsig > 1:
        # If we have a 2nd switching state, create another frequency vector with the shift.
        # offset[1] is the offset for the reference frequency.
        display_sky_frequencies.extend([_ + offset[1]/1e9 for _ in display_sky_frequencies])

    return display_sky_frequencies


def blank_window_plot(bank, window, state):

    for _ in range(10):
        g = Gnuplot.Gnuplot(persist=0)
        g.xlabel('GHz')
        g.ylabel('counts')
        g('set term png enhanced font '
          '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
          '9 size 600,200')
        g('set style data lines')
        g.title('Spectrometer {} '
                'Window {} {}'.format(bank, window, strftime('  %Y-%m-%d %H:%M:%S')))
        outfilename = '{}/plots/{}{}.png'.format(LCLDIR, bank, window)
        g('set out "' + outfilename + '"')
        g('unset key')
        g('set label "Manager state:  {}" at 0,0.5 center'.format(state))
        g.plot('[][0:1] 2')
        # Check to see if this created a non-zero size file.  If so, stop.
        #   If not, try again.
        sleep(cfg.PLOT_SLEEP_TIME)
        if os.stat(outfilename).st_size > 0:
            break


def blank_bank_plot(bank, state):
    for _ in range(10):
        g = Gnuplot.Gnuplot(persist=0)
        g.xlabel('GHz')
        g.ylabel('counts')
        g('set term png enhanced font '
          '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
          '9 size 600,200')
        g('set style data lines')
        g.title('Spectrometer {} {}'.format(bank, strftime('  %Y-%m-%d %H:%M:%S')))
        outfilename = "{}/plots/{}.png".format(LCLDIR, bank)
        g('set out "' + outfilename + '"')
        g('unset key')
        g('set label "Manager state:  {}" at 0,0.5 center'.format(state))
        g.plot('[][0:1] 2')
        sleep(cfg.PLOT_SLEEP_TIME)
        if os.stat(outfilename).st_size > 0:
            break


def get_value(context, bank, poller, key, directory_socket,
              bank_info, request_pending):
    """

    Args:
        context: A ZeroMQ context object.
        bank(str): The name of the VEGAS bank.
        poller: A ZeroMQ Poller object to check incoming messages.
        key(str): What type of data we want.  This is type 'state' or 'data'.
        directory_socket(socket): We need to know if there are any directory events.
        bank_info(dict): Holds the VEGAS bank URL and socket info.
        request_pending(bool): Are we already waiting for a response?

    Returns:
        We are mostly interested in a return message or data block, but
        we also return 'request_pending' and 'bank_info' in case anything has changed.

    """

    data_socket = bank_info['socket']

    # This is the REQ wrinkle: only send a request if the last
    # one was serviced. We might find ourselves back here if the
    # directory message was received instead of the data request,
    # in which case we must not make another request. In this
    # case, skip and drop into the poll to wait for the data.
    if not request_pending:
        logging.debug('requesting: {} from {}'.format(key, bank_info))
        data_socket.send(key, zmq.NOBLOCK)
        request_pending = True

    # This will block. May unblock if request is serviced, *or*
    # if directory service message is received.
    logging.debug('poller.sockets: %s', poller.sockets)
    socks = dict(poller.poll())
    logging.debug('{} socks {}'.format(strftime('%Y/%m/%d %H:%M:%S'), socks))

    # Handle a directory service message.
    # It occurs for restarts, new services, etc.
    # This doesn't usually happen.
    if directory_socket in socks:
        logging.debug('DIRECTORY SOCKET message')
        if socks[directory_socket] == zmq.POLLIN:
            logging.debug('POLLIN')
            key, payload = directory_socket.recv_multipart()
            bank_info, value = _handle_snapshoter(context, bank, bank_info, payload)
            if value == "ManagerRestart":
                poller.unregister(data_socket)
                poller.register(bank_info['socket'], zmq.POLLIN)
                request_pending = False

            logging.debug('get_value returning {}, {}, {}'.format(value, request_pending, bank_info))
            return value, request_pending, bank_info
        else:
            logging.debug('ERROR')
            return "Error", request_pending, bank_info

    # A much more common occurrence to get a VEGAS bank response.
    # The response will typically be STATE information or
    # spectral data. This is where we interpret what we receive.
    if data_socket in socks:
        logging.debug('DATA SOCKET message')
        if socks[data_socket] == zmq.POLLIN:
            logging.debug('POLLIN')
            data = _handle_data(data_socket, key)
            if data:
                if key.endswith('Data'):
                    value = data
                else:  # state
                    value = data.val_struct[0].val_string[0]
            else:
                value = None

            # indicate we can send a new request next time through loop.
            request_pending = False
            return value, request_pending, bank_info
        else:
            logging.debug('ERROR')
            return "Error", request_pending, bank_info


def open_a_socket(context, url, service_type=zmq.REQ):
    socket = context.socket(service_type)  # zmq.REQ || zmq.SUB
    socket.linger = 0  # do not wait for more data when closing
    socket.connect(url)
    return socket


def _handle_snapshoter(context, bank, bank_info, payload):
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
    # wrong interface, in which case 'bank_info['url']' will
    # be empty and the connection attempt below will
    # fail.
    logging.warning('SNAPSHOT {} {} {} interface {}'.format(reqb.major, reqb.minor,
                                                            reqb.snapshot_url[0], reqb.interface))

    major, minor = "VEGAS", "Bank{}Mgr".format(bank)
    if (reqb.major == major and
        reqb.minor == minor and
        reqb.interface == dsu.SERV_SNAPSHOT):

        new_url = _get_tcp_url(reqb.snapshot_url)

        if bank_info['url'] != new_url:
            restart_msg = "Manager restarted: %s.%s, %s, %s" % \
                          (reqb.major, reqb.minor, reqb.interface, new_url)
            logging.warning('{} {}'.format(datetime.now(), restart_msg))

            bank_info['url'] = new_url

            if bank_info['url']:
                logging.warning("new bank_info['url']: {}".format(bank_info['url']))
                bank_info['socket'].close()
                bank_info['socket'] = open_a_socket(context, bank_info['url'], zmq.REQ)
                logging.debug('bank_info', bank_info)
                return bank_info, "ManagerRestart"
            else:
                logging.warning("Manager {}.{} subscription "
                                "URL is empty! exiting...".format(major, minor))
    return bank_info, "NoRestart"


def _trim_spectra(myspectra):
    nsig, nwin, npol, _ = myspectra.shape

    # rebin each of the spectra
    sampled_spectra = []
    for sig in range(nsig):
        for win in range(nwin):
            for pol in range(npol):
                spectrum = myspectra[sig][win][pol]

                # interpolate over the center channel to remove the VEGAS spike
                centerchan = int(len(spectrum)/2)
                spectrum[centerchan] = (spectrum[centerchan - 1] + spectrum[centerchan + 1]) / 2.
                # rebin to NCHANS length
                logging.debug('raw spectrum length: {}'.format(len(spectrum)))
                # sample every sampsize channels of the raw spectrum, where
                # sampsize = 2 ^ (log2(raw_nchans) - log2(display_nchans))
                sampsize = 2 ** (math.log(len(spectrum), 2) - math.log(cfg.NCHANS, 2))
                sampled = spectrum[(sampsize/2):len(spectrum)-(sampsize/2)+1:sampsize]
                logging.debug('sampled spectrum length: {}'.format(len(sampled)))
                sampled_spectra.extend(sampled.tolist())
    return sampled_spectra


def _handle_data(sock, key):
    """Do something with the response from a VEGAS bank.

    Args:
        sock(socket): A bank socket object.
        key(str): Either state or data key.

    Returns:
        If it's data, a list containing project, scan number, integration
        number and a spectrum.
        If it's state info, we get the state string.
        If there is an error, None.

    """
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
            # This should only happen when we get state info.
            df = PBDataField()
            df.ParseFromString(rl[1])
            return df
        else:
            # We should only be here if we got a data response.
            df = pbVegasData()
            df.ParseFromString(rl[1])
            ff = array.array('f')  # 'f' is typecode for C float
            ff.fromstring(df.data_blob)

            n_sig_states = len(set(df.sig_ref_state))
            n_cal_states = len(set(df.cal_state))
            n_subbands = len(set(df.subband))

            logging.debug("Project ID is: {}".format(df.project_id))
            logging.debug("Scan number is: {}".format(df.scan_number))
            logging.debug("Polarization is: {}".format(df.polarization))
            logging.debug("Number of sub-bands is: {}".format(n_subbands))
            logging.debug("Number of sig switching states is: {}".format(n_sig_states))
            logging.debug("Number of cal states is: {}".format(n_cal_states))
            logging.debug("Number of polarizations: {}".format(df.number_stokes))

            problem = False
            if n_subbands < 1:
                problem = True
            if n_sig_states < 1:
                problem = True
            if n_cal_states < 1:
                problem = True
            if problem:
                return None

            n_chans, n_samplers, n_states = df.data_dims

            full_res_spectra = np.array(ff)

            logging.debug('full_res_spectra {}'.format(full_res_spectra[:10]))
            # change the dimensions of the spectra to be
            #   STATES (sigref, cal), SAMPLERS (windows, polarizations), CHANNELS
            full_res_spectra = full_res_spectra.reshape(df.data_dims[::-1])

            # estimate the number of polarizations used to grab the first
            # of each subband
            n_pols = (n_samplers/n_subbands)
            logging.debug('polarization estimate: {}'.format(n_pols))

            # Reshape the spectra into these dimensions:
            #   sigref, cals, windows, polarizations, channels
            full_res_spectra = full_res_spectra.reshape((n_sig_states, n_cal_states, n_subbands, n_pols, n_chans))

            # If we have more than two polarizations, only keep the first two.
            full_res_spectra = full_res_spectra[:,:,:,:2,:]
            if n_pols > 2:
                n_pols = 2

            # average the calon/caloff pairs
            # this reduces the state dimension by 1/2
            # i.e. 2,14,1024 becomes 1,14,1024 or 14,1024
            # TODO this assumes only cal and sig switching
            #   if other switching is added in the future, it could
            #   be an issue.  n_states should == 2.
            myspectra = np.mean(full_res_spectra, axis=1)

            if n_sig_states == 2:
                logging.debug('SIG SWITCHING')

            # The spectra array dimensions are now:
            #   sigref, windows, polarizations, channels
            files_available = True
            try:
                sky_freqs = _sky_frequencies(myspectra, df)
            except:
                logging.debug('Frequency information unavailable.  Substituting with dummy freq. data.')
                files_available = False
                sky_freqs = _make_dummy_frequencies(n_sig_states, n_subbands, n_pols)

            # Reduce the number of channels in all spectra to make them easier to display.
            # This is also where we remove the center spike.
            sampled_spectra = _trim_spectra(myspectra)

            # Join the frequencies to the spectra.
            spectrum = np.array(zip(sky_freqs, sampled_spectra))

            # The 2 in the following line accounts for the data and frequency axes.
            spectrum = spectrum.reshape((n_sig_states, n_subbands, n_pols, cfg.NCHANS, 2)).tolist()

            # sort each spectrum by frequency
            for sigidx in range(n_sig_states):
                for winidx in range(n_subbands):
                    for polidx in range(n_pols):
                        spectrum[sigidx][winidx][polidx] = sorted(spectrum[sigidx][winidx][polidx])

            project = str(df.project_id)
            scan = int(df.scan_number)
            integration = int(df.integration)

            # collect the polarization names to display, e.g. "L" or "R"
            sampler_table = _sampler_table(df)

            polname = []
            if files_available:
                _, _, iffile_info = filedata.info_from_files(project, scan)
                
                for pnum in range(1, n_pols+1):
                    port, bank = pnum, sampler_table['BANK_A'][0]
                    pname, _, _, _ = iffile_info[(pnum, bank)]
                    polname.append(pname*2)  # double the string, e.g. 'R' -> 'RR'
            else:
                for pnum in range(1, n_pols+1):
                    polname.append(str(pnum))

            response = (project, scan, integration, polname, np.array(spectrum))
            return response
    else:
        return None
