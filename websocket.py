from tornado import websocket
import tornado.web
import tornado.ioloop
from multiprocessing import Process
import time
import os

from pyzmq_stream_poller import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html", title = 'Vegas Data Display')

server_pub_port  = '5558'
        
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        self.startTimes, self.endTimes = [], []
        Process(target=server_pub, args=(server_pub_port,self,)).start()
        Process(target=client, args=(server_pub_port,self,)).start()
        print "WebSocket opened"

    def on_message(self, message):
        self.endTimes.append((message, time.time()))
        #print 'end times:  ', self.endTimes

    def write_message(self, msg):
        if msg != 'close':
            self.startTimes.append((msg[0], time.time()))
        super(ZMQWebSocket, self).write_message(unicode(msg))
        
    def on_close(self):
        print self.startTimes
        print self.endTimes
        print "WebSocket closed"

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
    app.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
