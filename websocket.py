from tornado import websocket
import tornado.web
import tornado.ioloop
from multiprocessing import Process
import time
import os

from pyzmq_stream_poller import server_pub, client

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')

server_pub_port  = '5559'
        
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        """
        This method is called when the JS creates a WebSocket object.
        """
        self.times = {}
        self.msgSize = None

        #  Launch our mock up zmq publisher in a separate process.
        Process(target=server_pub, args=(server_pub_port,)).start()

        #  Also, call client to subscribe to the zmq socket. NOTICE: we
        #  additionally pass in a reference to self (ZMQWebSocket instance).
        client(server_pub_port, self)
        print "WebSocket opened"

    def on_message(self, message):
        """
        This method is called when the server responds.  See send call in the
        onmessage function in Display.js in the client code.
        """
        self.times[int(message)].append(time.time())

    def write_message(self, msg):
        data = unicode(msg)
        self.msgSize = self.msgSize or len(data) * 2
        if msg != 'close':
            self.times[msg[0]] = [time.time()]
        super(ZMQWebSocket, self).write_message(data)
        
    def on_close(self):
        print "WebSocket closed"
        print "Message size (bytes)", self.msgSize
        print [e - s for _ , (s, e) in self.times.iteritems()]

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static"),
    "cookie_secret": "__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    "login_url": "/login",
    "xsrf_cookies": True,
    "debug" : True
}

app = tornado.web.Application([
    (r"/", MainHandler),
    (r"/websocket", ZMQWebSocket),
], **settings)

if __name__ == "__main__":
    app.listen(8889)
    tornado.ioloop.IOLoop.instance().start()

