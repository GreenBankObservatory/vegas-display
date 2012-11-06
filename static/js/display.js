var spectralData = new Array();
var heightScale  = .01;
var width  = 800;
var height = 600;
var vertMargin  = 50;
var hortMargin  = 50;
var heightScale = .005;

function clearCanvas(){
    var c = document.getElementById("fg");
    var ctx = c.getContext("2d");
    ctx.clearRect(0, 0, width, height);
};  
            
function drawDisplay(data){
    var c = document.getElementById("fg");
    var ctx = c.getContext("2d");

    var numChannels = data.length;
    var pointWidth  = (width - vertMargin) / numChannels;
    var pointHeight = heightScale * (height - hortMargin);
    var xStart      = hortMargin;
    var yStart      = height;
    var value;
    var i = spectralData.length;
    c.style.top = "-" + (height - vertMargin - (pointHeight * i + 1)) + "px";
    for(var j = 0; j < numChannels; j++){
        value = data[j];
        ctx.fillStyle = getFillColor(value);
	ctx.fillRect(xStart + (pointWidth * j),
	             yStart - (pointHeight * i),
		     pointWidth,
		     pointHeight)
    }
};

function drawAxis() {
    var c = document.getElementById("bg");
    var ctx = c.getContext("2d");
    var l = hortMargin; //Short hand
    ctx.moveTo(l, vertMargin);
    ctx.lineTo(l, height);
    ctx.moveTo(l, vertMargin);
    ctx.lineTo(width, vertMargin);
    ctx.stroke();

    ctx.font = "20px Arial";
    ctx.fillStyle = '#000000';
    ctx.fillText("channels", width / 2.0, vertMargin - 10)
 };
    
function getFillColor(value){
    var colors = ['#FF0000',
        	  '#00FF00',
		  '#0000FF',
                  '#800080',
                  '#FFFF00',
                  '#FFA500'];
    return colors[value - 5];
};

function addData(data){
    var maxSize = 1 / heightScale;
    if (spectralData.length >= maxSize){
        spectralData = new Array();
        clearCanvas();
    }
    spectralData.unshift(data);
};

function updateDisplay(data){
    addData(data);
    drawDisplay(data);
};

window.onload = function(){
    drawAxis();
    var ws = new WebSocket("ws://colossus.gb.nrao.edu:8888/websocket");
    //var ws = new WebSocket("ws://192.168.28.128:8888/websocket");
    ws.onopen = function() {
      //ws.send("Hello, world");
    };
    ws.onmessage = function (evt) {
        if (evt.data == 'close'){
            console.log('Closing WebSocket.');
            ws.close();
        } else {
            var data = eval(evt.data);
            updateDisplay(data[1]);
            console.log(data[0], data[1].length);
            ws.send(data[0]);
        }
    };
}
    