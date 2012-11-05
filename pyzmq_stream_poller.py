import zmq
import time
import sys
import random
import pickle
import zlib
from  multiprocessing import Process

from zmq.eventloop import ioloop, zmqstream
ioloop.install()

def server_pub(port, ws):
    context = zmq.Context()
    socket  = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)
    publisher_id = random.randrange(0,9999)
    print "Running server on port: ", port
    times = []
    # serves only 5 request and dies
    for reqnum in range(10):
        # Wait for next request from client
        #numchan = 32768  # max number of channels with VEGAS
        numchan = 1000
        data    = [reqnum, [random.randrange(5, 10) for i in xrange(numchan)]]
        #print 'zmq sending:', data[0]
        #times.append((reqnum, time.time()))
        socket.send_pyobj(data)
        time.sleep(2)
    #print 'start times:', times
    ws.write_message('close');
    ioloop.IOLoop.instance().stop()
        
def client(port_sub, ws):    
    context     = zmq.Context()
        
    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect ("tcp://localhost:%s" % port_sub)
    socket_sub.setsockopt(zmq.SUBSCRIBE, '')
    
    def handler(msg):
        msg = pickle.loads(msg[0])
        #print 'websocket sending:', msg[0]
        ws.write_message(msg)

    stream_sub = zmqstream.ZMQStream(socket_sub)
    stream_sub.on_recv(handler)
    print "Connected to publisher with port %s" % port_sub
    
    ioloop.IOLoop.instance().start()
    print "Worker has stopped processing messages."
