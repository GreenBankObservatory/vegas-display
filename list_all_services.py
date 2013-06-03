#! /usr/bin/env python
######################################################################
#
#  list_all_services.py -- Requests a list of all service URLs from
#  the directory service.
#
#  Usage:
#      list_all_services.py
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
from request_pb2 import *
from DataStreamUtils import get_directory_endpoints

def main():
    """ main method """

    context = zmq.Context(1)
    request = context.socket(zmq.REQ)
    req_url = get_directory_endpoints('request')
    request.connect(req_url)
    request.send("LIST");

    buffers = request.recv_multipart()

    for buf in buffers:
        if buf != "END":
            reqb = PBRequestService()
            reqb.ParseFromString(buf)
            print reqb.major, reqb.minor, reqb.errors, reqb.url

    request.close()

if __name__ == "__main__":
    main()
