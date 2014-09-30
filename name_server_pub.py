#! /usr/bin/env python
######################################################################
#
#  name_server_pub.py - demonstrates how to get published events from
#  the directory service.  The directory service may announce that it
#  is going down, coming up, or registering a new service.
#
#  Usage:
#      name_server_pub.py
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
from socket import gethostname, gethostbyname_ex

from DataStreamUtils import get_directory_endpoints

directory_name = "YgorDirectory"


def main():
    """ main method """

# Prepare our context and publisher
    context = zmq.Context(1)

    url = get_directory_endpoints("publisher")

    # socket to get the subscription for those values
    subscriber = context.socket(zmq.SUB)
    # now subscribe to any announcements from name server
    subscriber.setsockopt(zmq.SUBSCRIBE, "")
    subscriber.connect(url)

    # Now process the subscribed values:
    try:
        while True:
            # Read envelope with address
            msg = []
            msg = subscriber.recv_multipart()

            key = msg[0]
            payload = msg[1]

            if key == directory_name + ":NEW_INTERFACE":
                dev = PBRequestService()
                dev.ParseFromString(msg[1])
                print "new device: %s.%s" % (dev.major, dev.minor), dev.url
            if key == directory_name + ":SERVER_UP":
                print key, payload
            if key == directory_name + ":SERVER_DOWN":
                print key, payload
    except KeyboardInterrupt, e:
        subscriber.close()
        context.term()

if __name__ == "__main__":
    main()
