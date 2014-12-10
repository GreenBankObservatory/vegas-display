#! /usr/bin/env python

from time import strftime, sleep
import logging
import argparse

import zmq
import Gnuplot

import DataStreamUtils as dsutils

import server_config as cfg
import utils

def main(bank):
    mjr, mnr = "VEGAS", "Bank{}Mgr".format(bank)
    state_key = "{}.{}:P:state".format(mjr,mnr)
    data_key = "{}.{}:Data".format(mjr,mnr)
    context   = zmq.Context(1)

    # get URLs
    
    # directory request(device services) and publish(new interfaces) URLs
    _, directory_url, directory_event_url = dsutils.get_directory_endpoints()

    # VEGAS BankA snapshot URLs
    vegas_snap_url,_,_ = dsutils.get_service_endpoints(context,
                                                       directory_url,mjr, mnr,
                                                       dsutils.SERV_SNAPSHOT) 

    logging.info('directory (request/services)        url: {}'.format(directory_url))
    logging.info('directory (publish/newinterfaces)   url: {}'.format(directory_event_url))
    logging.info('vegas snapshot                      url: {}'.format(vegas_snap_url))

    # connect sockets
    directory_socket = utils.open_a_socket(context, directory_event_url, zmq.SUB)
    directory_socket.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    data_socket = utils.open_a_socket(context, vegas_snap_url, zmq.REQ)

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
        value, request_pending = utils.get_value(context, bank, poller, state_key,
                                                 directory_socket, data_socket,
                                                 request_pending, vegas_snap_url)
        if value:
            logging.debug('{} = {}'.format(state_key, value))

        gbank('set out "static/{}.png"'.format(bank))

        if cfg.ALWAYS_UPDATE: ready_for_value = True
        else: ready_for_value = (value == 'Running')

        if ready_for_value:
            value, request_pending = utils.get_value(context, bank, poller, data_key,
                                                     directory_socket, data_socket,
                                                     request_pending, vegas_snap_url)
            if value:
                proj, scan, integration, spec = value
                logging.debug('{} {} {} {}'.format(proj, scan, integration, spec.shape))

                if (prevscan,prevint) != (scan,integration) or cfg.ALWAYS_UPDATE:
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
                            utils.blank_plot(gwindow)
            else:
                gbank.title('Spec. {} {}'.format(bank, strftime('  %Y-%m-%d %H:%M:%S')))
                utils.blank_plot(gbank)

        else:
            gbank.title('Spec. {} {}'.format(bank, strftime('  %Y-%m-%d %H:%M:%S')))
            utils.blank_plot(gbank)
            for window in range(8):
                gwindow.title('Spectrometer {} '
                              'Window {} {}'.format(bank, window, strftime('  %Y-%m-%d %H:%M:%S')))
                gwindow('set out "static/{}{}.png"'.format(bank, window))
                utils.blank_plot(gwindow)

        # pace the data requests    
        sleep(cfg.UPDATE_RATE)


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
                        level=cfg.log_level[args.v])
    main(args.bank)
