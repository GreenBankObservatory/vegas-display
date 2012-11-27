define([], function() {
    return {init: function(){
                this.spectralData = new Array();
                this.heightScale  = .01;
                this.width  = 800;
                this.height = 600;
                this.vertMargin  = 50;
                this.hortMargin  = 50;
                this.heightScale = .01;

                console.log('hello');
                this.drawAxis();
                var ws = new WebSocket("ws://colossus.gb.nrao.edu:8888/websocket");
                //var ws = new WebSocket("ws://192.168.28.128:8888/websocket");
                ws.onopen = function() {
                    //ws.send("Hello, world");
                };
                var me = this;
                ws.onmessage = function (evt) {
                    if (evt.data == 'close'){
                        console.log('Closing WebSocket.');
                        ws.close();
                    } else {
                        var data = eval(evt.data);
                        me.updateDisplay(data[1]);
                        console.log(data[0], data[1].length);
                        ws.send(data[0]);
                    }
                };
            },
            clearCanvas: function(){
                var c = document.getElementById("fg");
                var ctx = c.getContext("2d");
                ctx.clearRect(0, 0, this.width, this.height);
            },
            drawDisplay: function(data){
                var c = document.getElementById("fg");
                var ctx = c.getContext("2d");
 
                var numChannels = data.length;
                var pointWidth  = (this.width - this.vertMargin) / numChannels;
                var pointHeight = this.heightScale * (this.height - this.hortMargin);
                var xStart      = this.hortMargin;
                var yStart      = this.height;
                var value;
                var i = this.spectralData.length;
                c.style.top = "-" + (this.height - this.vertMargin - (pointHeight * i + 1)) + "px";
                for(var j = 0; j < numChannels; j++){
                    value = data[j];
                    ctx.fillStyle = this.getFillColor(value);
                    ctx.fillRect(xStart + (pointWidth * j),
	                         yStart - (pointHeight * i),
               	                 pointWidth,
		                 pointHeight);
                }
            },
            drawAxis: function() {
                var c = document.getElementById("bg");
                var ctx = c.getContext("2d");
                var l = this.hortMargin; //Short hand
                ctx.moveTo(l, this.vertMargin);
                ctx.lineTo(l, this.height);
                ctx.moveTo(l, this.vertMargin);
                ctx.lineTo(this.width, this.vertMargin);
                ctx.stroke();

                ctx.font = "20px Arial";
                ctx.fillStyle = '#000000';
                ctx.fillText("channels", this.width / 2.0, this.vertMargin - 10)
            },
    
            getFillColor: function(value){
                var colors = ['#FF0000',
             	              '#00FF00',
		              '#0000FF',
                              '#800080',
                              '#FFFF00',
                              '#FFA500'];
                return colors[value - 5];
            },

            addData: function(data){
                var maxSize = 1 / this.heightScale;
                if (this.spectralData.length >= maxSize){
                    this.spectralData = new Array();
                    this.clearCanvas();
                }
                this.spectralData.unshift(data);
            },

            updateDisplay: function(data){
                this.addData(data);
                this.drawDisplay(data);
            },
        };
});

