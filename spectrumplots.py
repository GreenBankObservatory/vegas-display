#! /usr/bin/env python

import sys
from time import strftime, sleep
import logging
import argparse

import zmq
import Gnuplot

import gbtzmq.DataStreamUtils as gbtdsu

import server_config as cfg
import displayutils


def main(bank):
    mjr, mnr = "VEGAS", "Bank{}Mgr".format(bank)
    state_key = "{}.{}:P:state".format(mjr, mnr)
    data_key = "{}.{}:Data".format(mjr, mnr)
    context = zmq.Context(1)

    # directory service and VEGAS data connection info structures
    directory = {'url': None, 'event_url': None, 'socket': None}
    vegasdata = {'url': None, 'socket': None}

    # get the directory "request" (i.e. device services) and "publish" (i.e. new interfaces) URLs
    _, directory['url'], directory['event_url'] = gbtdsu.get_directory_endpoints()

    # get VEGAS bank snapshot URL
    vegasdata['url'], _, _ = gbtdsu.get_service_endpoints(context, directory['url'], mjr, mnr, gbtdsu.SERV_SNAPSHOT)

    # print what we know about the URLs
    logging.info('directory (request/services)        url: {}'.format(directory['url']))
    logging.info('directory (publish/newinterfaces)   url: {}'.format(directory['event_url']))
    logging.info('vegas snapshot                      url: {}'.format(vegasdata['url']))

    # connect to the directory event socket
    directory['socket'] = displayutils.open_a_socket(context, directory['event_url'], zmq.SUB)
    directory['socket'].setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    # connect to the VEGAS data socket
    vegasdata['socket'] = displayutils.open_a_socket(context, vegasdata['url'], zmq.REQ)

    # print what we know about the directory service and VEGAS data sockets
    logging.info('directory socket: {}'.format(directory['socket']))
    logging.info('snap socket     : {}'.format(vegasdata['socket']))

    # create poller to watch both sockets
    poller = zmq.Poller()
    poller.register(directory['socket'], zmq.POLLIN)
    poller.register(vegasdata['socket'], zmq.POLLIN)

    # if we keep track of the scan and integration, we will know when they change
    prevscan, prevint = None, None

    # we want to know when we are waiting for a response
    request_pending = False

    # initialize a plot object for the bank (all windows)
    gbank = Gnuplot.Gnuplot(persist=0)
    gbank.xlabel('GHz')
    gbank.ylabel('counts')
    gbank('set term png enhanced font '
          '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
          '9 size 600,200')
    gbank('set data style lines')

    # initialize a plot object for each bank window
    gwindow = Gnuplot.Gnuplot(persist=0)
    gwindow.xlabel('GHz')
    gwindow.ylabel('counts')
    gwindow('set term png enhanced font '
            '"/usr/share/fonts/liberation/LiberationSans-Regular.ttf" '
            '9 size 600,200')
    gwindow('set data style lines')

    while True:
        try:
            # Try to get VEGAS state for this bank.
            # Note that we send the state_key.
            # We are trying to find out if the bank is available to ask for data.
            state, request_pending, vegasdata = displayutils.get_value(context, bank, poller, state_key,
                                                                       directory['socket'], vegasdata,
                                                                       request_pending)

            # If the manager was restarted, try again to get the state.
            if state == "ManagerRestart":
                continue

            if state:
                logging.debug('{} = {}'.format(state_key, state))

            gbank('set out "static/{}.png"'.format(bank))

            # ALWAYS_UPDATE is useful for debugging.
            # Typically, we only want to display data when the VEGAS bank is "Running".
            if cfg.ALWAYS_UPDATE:
                ready_for_value = True
            else:
                ready_for_value = (state == 'Running')
            
            if ready_for_value:
                # Now that we know the bank is ready, we can request data.
                # This time we send the data_key.
                value, request_pending, vegasdata = displayutils.get_value(context, bank, poller, data_key,
                                                                           directory['socket'], vegasdata,
                                                                           request_pending)

                # In case the manager was restarted, try again to get the state.
                if value == "ManagerRestart":
                    continue

                if value:
                    # It looks like we got some data.
                    # Unpack it and show what we have.
                    proj, scan, integration, spec = value
                    logging.debug('{} {} {} {}'.format(proj, scan, integration, spec.shape))

                    # If either the scan or integration number changed, we have something new.
                    if (prevscan, prevint) != (scan, integration) or cfg.ALWAYS_UPDATE:

                        # Remember the current scan and integration numbers for the next iteration.
                        prevscan = scan
                        prevint = integration

                        # We don't need a plot legend if there is only one spectrum.
                        if len(spec) == 1:
                            gbank('unset key')
                        else:
                            gbank('set key default')

                        # Create a plot title to summarize the scan.
                        gbank.title('Spec. {} '
                                    'Scan {} '
                                    'Int. {} {}'.format(bank, scan, integration, strftime('  %Y-%m-%d %H:%M:%S')))

                        # Plot all of the spectra (one for each spectral window) on the same plot window.
                        ds = []
                        for win, ss in enumerate(spec):
                            dd = Gnuplot.Data(ss, title='{}'.format(win))
                            ds.append(dd)
                        gbank.plot(*ds)

                        # Now, make a plot for each individual spectral window.
                        for window in range(8):
                            gwindow.title('Spec. {} Win. {} '
                                          'Scan {} '
                                          'Int. {} {}'.format(bank, window, scan, 
                                                              integration,
                                                              strftime('  %Y-%m-%d %H:%M:%S')))
                            gwindow('set out "static/{}{}.png"'.format(bank, window))

                            # If there is no data for this window, create a blank plot.
                            if window < len(spec):
                                gwindow('set key default')
                                gwindow.plot(spec[window])
                                gwindow.clear()
                            else:
                                displayutils.blank_window_plot(bank, window, state)
                else:
                    # If there is no bank data at the moment, create a blank plot.
                    displayutils.blank_bank_plot(bank, state)
            else:
                # If the bank is not "running", create blank plots the bank and all windows.
                displayutils.blank_bank_plot(bank, state)
                for window in range(8):
                    displayutils.blank_window_plot(bank, window, state)

            # pace the data requests    
            sleep(cfg.UPDATE_RATE)

        except KeyboardInterrupt:
            directory['socket'].close()            
            vegasdata['socket'].close()
            context.term()
            sys.exit(1)

        # If something goes horribly wrong, dump out potentially useful info and exit.
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
