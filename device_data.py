#! /usr/bin/env python
######################################################################
#
#  device_data.py -- a simple client to published Manager data (parameters and samplers)
#
#  Usage:
#      device_data.py "major.minor:[S|P]:<sampler/parameter name>"
#
#  For example:
#      device_data.py "Undulator.Undulator:S:measuredFrequencyB"
#
#  It will start printing out the received data.
#
#  Copyright (C) 2012 Associated Universities, Inc. Washington DC, USA.
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#  Correspondence concerning GBT software should be addressed as follows:
#  GBT Operations
#  National Radio Astronomy Observatory
#  P. O. Box 2
#  Green Bank, WV 24944-0002 USA
#
######################################################################

import zmq
from PBDataDescriptor_pb2 import *
from request_pb2 import *
import DataStreamUtils as ds

def main():
    """ main method """

# Prepare our context and publisher
    context = zmq.Context(1)

    und_keys = [
            "Undulator.Undulator:S:measuredFrequencyA",
            "Undulator.Undulator:S:measuredFrequencyB",
            "Undulator.Undulator:P:state",
            "Undulator.Undulator:P:status",
            "Undulator.UndulatorB:P:actual_level"
            ]

    chomp_keys = [
        "Chomper.Chomper:P:state",
        "Chomper.Chomper:P:status"
        ]

    directory_urls = ds.get_directory_endpoints()
    undulator_urls = ds.get_service_endpoints(context, directory_urls[ds.NS_REQUEST],
                                           "Undulator", "Undulator")
    chomper_urls = ds.get_service_endpoints(context, directory_urls[ds.NS_REQUEST],
                                         "Chomper", "Chomper")
    print undulator_urls
    print chomper_urls

    # sockets to get current snapshot of values
    und_snap = context.socket(zmq.REQ)
    und_snap.linger = 0
    und_snap.connect(undulator_urls[ds.SERV_SNAPSHOT])

    chomp_snap = context.socket(zmq.REQ)
    chomp_snap.linger = 0
    chomp_snap.connect(chomper_urls[ds.SERV_SNAPSHOT])

    # use one subscriber socket to connect to all publishers
    subscriber = context.socket(zmq.SUB)
    subscriber.connect(undulator_urls[ds.SERV_PUBLISHER]) # undulator
    subscriber.connect(chomper_urls[ds.SERV_PUBLISHER])   # chomper
    subscriber.connect(directory_urls[ds.NS_PUBLISHER])   # directory service

    init_vals = {}
    
    # Subscribe and get current values
    for key in und_keys:
        init_vals[key] = []
        init_vals[key] += ds.subscribe_to_key(und_snap, subscriber, key)

    for key in chomp_keys:
        init_vals[key] = []
        init_vals[key] += ds.subscribe_to_key(chomp_snap, subscriber, key)

    # now subscribe to any announcements from name server
    subscriber.setsockopt(zmq.SUBSCRIBE, "YgorDirectory:NEW_INTERFACE")

    # don't need the snapshot interface anymore
    und_snap.close()
    chomp_snap.close()

    # print out the initial values
    for i in init_vals:
        for k in init_vals[i]:
            print "INIT VAL - [%s]:" % (i), k

    # Now process the subscribed values:
    try:
        while True:
            # Read envelope with address
            msg = []
            msg = subscriber.recv_multipart()

            key = msg[0]
            payload = msg[1]

            if key == "YgorDirectory:NEW_INTERFACE":
                dev = PBRequestService()
                dev.ParseFromString(msg[1])
                print "new device: %s.%s i:%i" \
                    % (dev.major, dev.minor, dev.interface), dev.url

            else:
                df = PBDataField()
                df.ParseFromString(payload)
                print("[%s] %s\n" % (key, df))
    except KeyboardInterrupt, e:
        subscriber.close()
        context.term()

if __name__ == "__main__":
    main()
