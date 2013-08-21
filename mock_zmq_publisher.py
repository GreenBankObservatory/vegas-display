import time
import random
import zmq

from zmq.eventloop import ioloop
ioloop.install()


NCHANS = 1024 # 32768 is max number of channels with VEGAS

def mock_zmq_publisher(port):
    context = zmq.Context()
    socket  = context.socket(zmq.REP)  # request-reply pattern
    socket.bind("tcp://*:%s" % port)

    print "Running server on port: ", port

    while True:
        socket.recv()  # receive any message to trigger sending data

        # Wait for next request from client
        data = [random.randrange(0,98765) for i in xrange(NCHANS)]

        # the following will eventually be replaced with a protobuf
        socket.send_pyobj(data)

    socket.send_pyobj('close')
