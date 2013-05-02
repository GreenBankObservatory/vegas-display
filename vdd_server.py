import zmq
from zmq.eventloop import zmqstream

from tornado import websocket
import tornado.web
import tornado.ioloop

from multiprocessing import Process
import pickle
import time
import os

from publisher import mock_zmq_publisher

PUBLISHER_PORT  = '5559'

def zmqclient(port_sub, ws):

    context = zmq.Context()
        
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


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')
      
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        """
        This method is called when the JS creates a WebSocket object.
        """
        self.times = {}
        self.msgSize = None

        #  Launch our mock up zmq publisher in a separate process.
        Process(target=mock_zmq_publisher, args=(PUBLISHER_PORT,)).start()

        #  Also, call client to subscribe to the zmq socket. NOTICE: we
        #  additionally pass in a reference to self (ZMQWebSocket instance).
        zmqclient(PUBLISHER_PORT, self)
        print "WebSocket opened"

    def on_message(self, message):
        """
        This method is called when the server responds.  See send call in the
        onmessage function in Display.js in the client code.
        """
        self.times[int(message)].append(time.time())

    def write_message(self, msg):
        """ 
        The following extends the write_message() method of the
        websocket.WebSocketHandler() base class [using super()]
        with the preamble code that converts the message to unicode,
        sets the message size and records timing information.
        
        """
        
        data = unicode(msg)
        # the size of an 8bit Unicode string in bytes is length *2
        # the following is an idiom for
        #   if x then do y, else no change (set x=x)
        self.msgSize = self.msgSize or len(data) * 2
        if msg != 'close':
            self.times[msg[0]] = [time.time()]
               
        # python 3 syntax would be super().write_message(data)
        super(ZMQWebSocket, self).write_message(data)
        
    def on_close(self):
        print "WebSocket closed"
        print "Message size (bytes)", self.msgSize
        print [e - s for _ , (s, e) in self.times.iteritems()]

if __name__ == "__main__":

    settings = {
        "static_path": os.path.join(os.path.dirname(__file__), "static"),
        "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
        "login_url": "/login",
        "xsrf_cookies": True,
        "debug" : True
    }

    application = tornado.web.Application([
        (r"/", MainHandler),
        (r"/websocket", ZMQWebSocket),
    ], **settings)
    
    application.listen(8889)
    tornado.ioloop.IOLoop.instance().start()
