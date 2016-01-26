#! /usr/bin/env python

from time import strftime, sleep
import logging
import argparse
import sys
import traceback
import os

import zmq
import Gnuplot
import numpy as np

import gbtzmq.DataStreamUtils as gbtdsu

import server_config as cfg
import displayutils


LCLDIR = os.path.dirname(os.path.abspath(__file__))


def main(bank):
    mjr, mnr = "VEGAS", "Bank{}Mgr".format(bank)
    state_key = "{}.{}:P:state".format(mjr, mnr)
    data_key = "{}.{}:Data".format(mjr, mnr)
    context = zmq.Context(1)

    # get URLs
    directory = {'url': None, 'event_url': None, 'socket': None}
    vegasdata = {'url': None, 'socket': None}
    # directory request(device services) and publish(new interfaces) URLs
    _, directory['url'], directory['event_url'] = gbtdsu.get_directory_endpoints()

    # VEGAS BankA snapshot URLs
    vegasdata['url'], _, _ = gbtdsu.get_service_endpoints(context, directory['url'], mjr, mnr, gbtdsu.SERV_SNAPSHOT)

    logging.info('directory (request/services)        url: {}'.format(directory['url']))
    logging.info('directory (publish/newinterfaces)   url: {}'.format(directory['event_url']))
    logging.info('vegas snapshot                      url: {}'.format(vegasdata['url']))

    # connect sockets
    directory['socket'] = displayutils.open_a_socket(context, directory['event_url'], zmq.SUB)
    directory['socket'].setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    vegasdata['socket'] = displayutils.open_a_socket(context, vegasdata['url'], zmq.REQ)

    logging.info('directory socket: {}'.format(directory['socket']))
    logging.info('snap socket     : {}'.format(vegasdata['socket']))

    # create poller to watch sockets
    poller = zmq.Poller()
    poller.register(directory['socket'], zmq.POLLIN)
    poller.register(vegasdata['socket'], zmq.POLLIN)

    request_pending = False
    gwaterfall = Gnuplot.Gnuplot(persist=0)
    gwaterfall('set term png enhanced font '
               '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf"')
    gwaterfall('set data style image')
    gwaterfall('set xrange [0:{}]'.format(cfg.NCHANS))
    gwaterfall('set yrange [0:{}]'.format(cfg.NROWS))
    gwaterfall.xlabel('channel')
    gwaterfall.ylabel('integrations past')

    data_buffer = []
    for win in range(8):
        data_buffer.append(np.zeros(cfg.NROWS*cfg.NCHANS).reshape((cfg.NROWS, cfg.NCHANS)))

    prevscan, prevint = None, None
    update_reference = False
    reference_integration = None
    while True:
        try:
            state, request_pending, vegasdata = displayutils.get_value(context, bank, poller, state_key,
                                                                       directory['socket'], vegasdata,
                                                                       request_pending)

            # if the manager was restarted, try again to get the state
            if state == "ManagerRestart":
                continue

            if state:
                logging.debug('{} = {}'.format(state_key, state))

            if cfg.ALWAYS_UPDATE:
                ready_for_value = True
            else:
                ready_for_value = (state == 'Running')

            if ready_for_value:
                value, request_pending, vegasdata = displayutils.get_value(context, bank, poller, data_key,
                                                                           directory['socket'], vegasdata,
                                                                           request_pending)

                # if the manager was restarted, try again to get the state
                if value == "ManagerRestart":
                    continue

                if value:
                    proj, scan, integration, polname, spec = value
                    logging.debug('{} {} {} {} {}'.format(proj, scan, integration,
                                                          ','.join([pn for pn in polname]),
                                                          spec.shape))
                    # The second dimension is the number of windows or subbands.
                    #   We don't use it beacuse we loop over the spectra instead.
                    # The last dimension is always 2 to include frequencies.
                    # The first dimension is the number of frequency switching states.
                    nsig, _, npol, nchan, _ = spec.shape

                    if (prevscan, prevint) != (scan, integration) or cfg.ALWAYS_UPDATE:
                        if prevscan != scan:
                            update_reference = True
                            logging.debug('new reference. scan changed: {}'.format(scan))

                        prevscan = scan
                        prevint = integration
                        for win, ss in enumerate(spec[0]):  # get only the first frequency state
                            # in case we have full stokes, only average the first two polarization states
                            if npol >= 2:
                                npolave = 2
                            else:
                                npolave = npol
                            avepol = np.mean(ss[:npolave], axis=0)  # average over polarizations
                            
                            data_buffer[win] = np.roll(data_buffer[win], shift=1, axis=0)
                            # Get the data portion of the pol-averaged spectrum.
                            # We don't care about frequencies for the waterfall plot.
                            # TODO remove this->  we replaced right hand side: = spec[win][:, 1]
                            data_buffer[win][0] = avepol[:,1]

                            if update_reference:
                                logging.debug('updated reference')
                                reference_integration = np.copy(data_buffer[win][0])
                                update_reference = False

                            data_buffer[win][0] -= reference_integration

                            # this avoids a repeated warning message about the colorbox range
                            # (cbrange) being [0:0] when the data are all zeros
                            if np.ptp(data_buffer[win]) == 0:
                                gwaterfall('set cbrange [-1:1]')
                            else:
                                gwaterfall('set cbrange [*:*]')

                            gwaterfall.title('Spec. {} Win. {} '
                                             'Scan {} '
                                             'Int. {} {}'.format(bank, win, scan,
                                                                 integration,
                                                                 strftime('  %Y-%m-%d %H:%M:%S')))
                            gwaterfall('set out "{}/static/waterfall{}{}.png"'.format(LCLDIR, bank, win))
                            gdata = Gnuplot.GridData(np.transpose(data_buffer[win]), binary=0, inline=0)

                            gwaterfall.plot(gdata)

            # pace the data requests
            sleep(cfg.UPDATE_RATE)

        except KeyboardInterrupt:
            directory['socket'].close()
            vegasdata['socket'].close()
            context.term()
            sys.exit(1)
        except TypeError:
            print 'TypeError'
            print (context, bank, poller, state_key, directory, vegasdata, request_pending)
            print [type(x) for x in
                   (context, bank, poller, state_key, directory, vegasdata, request_pending)]
            sys.exit(2)
        except Exception as e:
            print "Error", traceback.format_exception(*sys.exc_info())
            sys.exit(3)

if __name__ == '__main__':
    # read command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("bank", help="port number to use on the server",
                        choices=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                                 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
                        type=str.upper)
    parser.add_argument("-v", help="verbosity output level", type=str,
                        choices=('err', 'warn', 'info', 'debug'), default='info')
    args = parser.parse_args()
    logging.basicConfig(format='%(asctime)s %(message)s',
                        datefmt='%m/%d/%Y %H:%M:%S',
                        level=cfg.log_level[args.v])
    main(args.bank)
