#! /usr/bin/env python
import traceback
import sys
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
    directory = {'url' : None, 'event_url' : None, 'socket' : None}
    vegasdata = {'url' : None, 'socket' : None}
    # directory request(device services) and publish(new interfaces) URLs
    _, directory['url'], directory['event_url'] = dsutils.get_directory_endpoints()

    # VEGAS BankA snapshot URLs
    vegasdata['url'],_,_ = dsutils.get_service_endpoints(context,
                                                         directory['url'],mjr, mnr,
                                                         dsutils.SERV_SNAPSHOT) 

    logging.info('directory (request/services)        url: {}'.format(directory['url']))
    logging.info('directory (publish/newinterfaces)   url: {}'.format(directory['event_url']))
    logging.info('vegas snapshot                      url: {}'.format(vegasdata['url']))

    # connect sockets
    directory['socket'] = utils.open_a_socket(context, directory['event_url'], zmq.SUB)
    directory['socket'].setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    vegasdata['socket'] = utils.open_a_socket(context, vegasdata['url'], zmq.REQ)

    logging.info('directory socket: {}'.format(directory['socket']))
    logging.info('snap socket     : {}'.format(vegasdata['socket']))

    # create poller to watch sockets
    poller = zmq.Poller()
    poller.register(directory['socket'], zmq.POLLIN)
    poller.register(vegasdata['socket'], zmq.POLLIN)

    prevscan, prevint = None, None

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

    while True:
        try:
            state, request_pending, vegasdata = utils.get_value(context, bank, poller, state_key,
                                                                directory['socket'], vegasdata,
                                                                request_pending)

            # if the manager was restarted, try again to get the state
            if state == "ManagerRestart":
                continue

            if state:
                logging.debug('{} = {}'.format(state_key, state))

            gbank('set out "static/{}.png"'.format(bank))

            if cfg.ALWAYS_UPDATE: ready_for_value = True
            else: ready_for_value = (state == 'Running')
            
            if ready_for_value:
                value, request_pending, vegasdata = utils.get_value(context, bank, poller, data_key,
                                                                    directory['socket'], vegasdata,
                                                                    request_pending)

                # if the manager was restarted, try again to get the state
                if value == "ManagerRestart":
                    continue

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
                                gwindow.clear()
                            else:
                                utils.blank_window_plot(bank, window, state)
                else:
                    utils.blank_bank_plot(bank, state)
            else:
                utils.blank_bank_plot(bank, state)
                for window in range(8):
                    utils.blank_window_plot(bank, window, state)

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
        except:
            print "Error"
            sys.exit(3)


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
        
