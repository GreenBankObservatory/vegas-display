#! /usr/bin/env python

import zmq
from PBDataDescriptor_pb2 import *
from DataStreamUtils import get_service_endpoints, get_directory_endpoints

def main():
    """ main method """

    context = zmq.Context(1)
    keys = ["ScanCoordinator.ScanCoordinator:P:state"]

    req_url = get_directory_endpoints('request')
    sub_url, _, _ = get_service_endpoints(context, req_url, "ScanCoordinator", "ScanCoordinator", 0)
#    sub_url = "ipc:///tmp/VEGAS.BankAMgr.publisher.eLhBx5"
    subscriber = context.socket(zmq.SUB)
    subscriber.connect(sub_url)

    for key in keys:
        subscriber.setsockopt(zmq.SUBSCRIBE, key)

    try:
        while True:
            # Read envelope with address
            [key, payload] = subscriber.recv_multipart()
            df = PBDataField()
            df.ParseFromString(payload)
            print("[%s] %s\n" % (key, df))
    except KeyboardInterrupt, e:
        subscriber.close()
        context.term()

if __name__ == "__main__":
    main()
