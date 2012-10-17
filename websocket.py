from tornado import websocket
import tornado.web
import tornado.ioloop
from multiprocessing import Process
import time

from pyzmq_stream_poller import *

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        html = """
<html>
  <head>
    <title>Websocket - toy</title>
    <script type="text/javascript">
      window.onload = function() {
        var ws = new WebSocket("ws://192.168.28.128:8888/websocket");
        ws.onopen = function() {
          //ws.send("Hello, world");
        };
        ws.onmessage = function (evt) {
          if (evt.data == 'close'){
            ws.close();
          } else {
            var data = eval(evt.data);
            console.log(data[0], data[1].length);
            ws.send(data[0]);
          }
        };
      }
    </script>
  </head>
  <body>
  </body>
</html>

        """
        self.write(html)

server_push_port = '5556'
server_pub_port  = '5558'
        
class ZMQWebSocket(websocket.WebSocketHandler):
    def open(self):
        self.startTimes, self.endTimes = [], []
        Process(target=server_push, args=(server_push_port,)).start()
        Process(target=server_pub, args=(server_pub_port,)).start()
        Process(target=client, args=(server_push_port,server_pub_port,self,)).start()
        print "WebSocket opened"

    def on_message(self, message):
        self.endTimes.append((message, time.time()))
        print 'end times:  ', self.endTimes
        #self.write_message(u"You said: " + message)

    def on_close(self):
        print "WebSocket closed"

app = tornado.web.Application([
    (r"/", MainHandler),
    (r"/websocket", ZMQWebSocket),
        ])

if __name__ == "__main__":
    app.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
