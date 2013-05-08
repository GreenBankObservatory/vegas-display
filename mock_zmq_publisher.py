import time
import random
import zmq

from zmq.eventloop import ioloop
ioloop.install()

NREQUESTS = 150
NCHANS = 1024 # 32768 is max number of channels with VEGAS

def mock_zmq_publisher(port):
    context = zmq.Context()
    socket  = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)
    
    print "Running server on port: ", port
    
    # serves NREQUESTS requests and dies
    for reqnum in range(NREQUESTS):

        # Wait for next request from client
        data = [reqnum, [random.randrange(5,10) for i in xrange(NCHANS)]]
        
        # the following will eventually be replaced with a protobuf
        socket.send_pyobj(data)
        print('sent data',reqnum)
        time.sleep(.5)
        
    socket.send_pyobj('close')
