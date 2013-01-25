import zmq
import tornado.ioloop
import time
import random
import pickle

from zmq.eventloop import ioloop, zmqstream
ioloop.install()

def server_pub(port):
    context = zmq.Context()
    socket  = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)
    publisher_id = random.randrange(0,9999)
    print "Running server on port: ", port
    # serves only 5 request and dies
    for reqnum in range(300):
        # Wait for next request from client
        #numchan = 32768  # max number of channels with VEGAS
        numchan = (1024, 2048)[1]
        data    = [reqnum, [random.randrange(5, 10) for i in xrange(numchan)]]
        # the following will eventually be replaced with a protobuf
        socket.send_pyobj(data)
        time.sleep(.5)
    socket.send_pyobj('close')
    #tornado.ioloop.IOLoop.instance().stop()
        
def client(port_sub, ws):    
    context     = zmq.Context()
        
    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect ("tcp://localhost:%s" % port_sub)
    socket_sub.setsockopt(zmq.SUBSCRIBE, '')
    
    def handler(msg):
        # the following will eventually read a protobuf instead of a zmq
        # python object
        msg = pickle.loads(msg[0])
        ws.write_message(msg)

    stream_sub = zmqstream.ZMQStream(socket_sub)
    stream_sub.on_recv(handler)
    print "Connected to publisher with port %s" % port_sub

