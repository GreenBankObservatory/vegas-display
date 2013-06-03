######################################################################
#
#  DataStreamUtils.py - utilities to help data streaming clients get
#  to the data streaming services.
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

import os
import zmq
import ConfigParser
import re

from request_pb2 import *
from PBDataDescriptor_pb2 import *

NS_REGISTER = 0
NS_REQUEST = 1
NS_PUBLISHER = 2

SERV_PUBLISHER = 0
SERV_SNAPSHOT = 1
SERV_CONTROL = 2

def get_service_endpoints(context, req_url, device, subdevice, interface = -1):
    """
    Request 0MQ endpoint URLs from the YgorDirectory service.  The
    device and subdevice are used to query the directory for the URLs.
    Each device will have 3 URLs. 0: the publishing url; 1: the
    snapshot URL; 2: the control URL.  If the interface is specified
    (via the 'interface' parameter), the return value is the URL
    specified.  If not, it is a list of the 3 URLs.
    """

    request = context.socket(zmq.REQ)
    request.connect(req_url)
    reqb = PBRequestService()
    reqb.major = device
    reqb.minor = subdevice

    if interface > -1 and interface < 3:
        reqb.interface = interface

    request.send(reqb.SerializeToString())
    reply = request.recv()
    reqb.ParseFromString(reply)
    request.close()

    if interface > -1 and interface < 3:
        return reqb.url[0]
    else:
        return reqb.url


def get_directory_endpoints(interface = None):
    """
    get_directory_endpoints(interface)

    Returns the endpoint URL(s) for the YgorDirectory 0MQ name
    service.  YgorDirectory provides 3 interfaces: 'register', which
    allows a service to register itself with the name service;
    'request', which allows a client to request a registered service
    by name; and 'publisher' which any subscriber may use to track
    YgorDirectory events (server up/down, new service registered,
    etc.).  Caller may specify which of these it wants, in which case
    the function returns the URL as a string; or request all of them
    if the 'interface' parameter is omitted, in which case the return
    value is a list of the URLs, in the order given above.
    """

    ygor_telescope = os.getenv("YGOR_TELESCOPE")

    if not ygor_telescope:
        raise Exception("YGOR_TELESCOPE is not defined!")

    interfaces = ['register', 'request', 'publisher']
    # read the config file for the YgorDirectory request URL
    config = ConfigParser.ConfigParser()
    config.readfp(open(ygor_telescope + "/etc/config/ZMQEndpoints.conf"))

    if interface and interface in interfaces:
        return config.get('YgorDirectory', interface)

    return [config.get('YgorDirectory', p) for p in interfaces]


def subscribe_to_key(snap, sub, key):
    """
    subscribe_to_key(snap, sub, key)

    Subscribes to the key 'key' using zmq socket 'sub', then retrieves
    a snapshot of the key's value from the server using the zmq socket
    'snap'.  The snapshot solves the late-joiner problem.

    returns a list [PBDataDescriptor_pb2,...]
    """
    # first subscribe.  It does no harm if the key is bogus.
    sub.setsockopt(zmq.SUBSCRIBE, key)
    # next, send a request for the latest value(s) snapshot
    snap.send(key)
    rl = []
    rl = snap.recv_multipart()
    el = len(rl)

    if el == 1:  # Got an error
        if rl[0] == "E_NOKEY":
            raise Exception("No key/value pair %s found on server!" % (key))
    if el > 1:
        # first element is the key
        # the following elements are the values
        rval = []

        for i in range(1, el):
            df = PBDataField()
            df.ParseFromString(rl[i])
            rval.append(df)

    return rval

def get_data_snapshot(key, sock = None):
    """ Obtains and returns one snapshot of data """

    if sock:
        snap = sock
        close_socket = False
    else:
        # sockets to get current snapshot of values
        context = zmq.Context(1)

        try:
            major, minor, dtype, name = re.split("[.:]", key)
        except ValueError:
            major, minor, dtype = re.split("[.:]", key)

        directory_url = get_directory_endpoints("request")
        device_url = get_service_endpoints(context, directory_url,
                                       major, minor, SERV_SNAPSHOT)

        snap = context.socket(zmq.REQ)
        snap.linger = 0
        snap.connect(device_url)
        close_socket = True

    snap.send(key)
    rl = []
    rl = snap.recv_multipart()

    if close_socket: # our socket, we should close.
        snap.close()

    el = len(rl)

    if el == 1:  # Got an error
        if rl[0] == "E_NOKEY":
            print "No key/value pair %s found on server!" % (key)
            return None
    elif el > 1:
        # first element is the key
        # the following elements are the values
        df = PBDataField()
        df.ParseFromString(rl[1])
        return df
    else:
        return None
