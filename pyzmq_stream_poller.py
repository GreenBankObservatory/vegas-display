import zmq
import time
import sys
import random
import pickle
import zlib
from  multiprocessing import Process

from zmq.eventloop import ioloop, zmqstream
ioloop.install()

def server_push(port):
    context = zmq.Context()
    socket  = context.socket(zmq.PUSH)
    socket.bind("tcp://*:%s" % port)
    print "Running server on port: ", port
    # serves only 5 request and dies
    for reqnum in range(10):
        if reqnum < 6:
            socket.send("Continue")
        else:
            socket.send("Exit")
            break
        time.sleep (1) 

def server_pub(port):
    context = zmq.Context()
    socket  = context.socket(zmq.PUB)
    socket.bind("tcp://*:%s" % port)
    publisher_id = random.randrange(0,9999)
    print "Running server on port: ", port
    times = []
    # serves only 5 request and dies
    for reqnum in range(10):
        # Wait for next request from client
        numchan = 32768  # max number of channels with VEGAS
        data    = [reqnum, [random.randrange(5, 10) * 0.5 for i in xrange(numchan)]]
        print 'zmq sending:', data[0]
        times.append((reqnum, time.time()))
        socket.send_pyobj(data)
        time.sleep(1)
    print 'start times:', times

        
def client(port_push, port_sub, ws):    
    context     = zmq.Context()
    socket_pull = context.socket(zmq.PULL)
    socket_pull.connect ("tcp://localhost:%s" % port_push)
    
    def getcommand(msg):
        #print "Received control command: %s" % msg
        if msg[0] == "Exit":
            print "Received exit command, client will stop receiving messages"
            ws.write_message('close');
            ioloop.IOLoop.instance().stop()

    stream_pull = zmqstream.ZMQStream(socket_pull)
    stream_pull.on_recv(getcommand)
    print "Connected to server with port %s" % port_push
        
    socket_sub = context.socket(zmq.SUB)
    socket_sub.connect ("tcp://localhost:%s" % port_sub)
    socket_sub.setsockopt(zmq.SUBSCRIBE, '')
    
    def handler(msg):
        msg = pickle.loads(msg[0])
        print 'websocket sending:', msg[0]
        ws.write_message(unicode(msg))

    stream_sub = zmqstream.ZMQStream(socket_sub)
    stream_sub.on_recv(handler)
    print "Connected to publisher with port %s" % port_sub
    
    ioloop.IOLoop.instance().start()
    print "Worker has stopped processing messages."
