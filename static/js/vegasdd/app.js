Ext.application({
    requires: ['Ext.container.Viewport'],
    appFolder: 'static/js/vegasdd',
    name: 'vegasdd',
    controllers: [
	'CanvasDisplay',
    ],
    
    launch: function() {
	var me = this;
	var display = Ext.create('vegasdd.view.data.CanvasDisplay');
	this.getController('CanvasDisplay').setDisplay(display);
        Ext.create('Ext.container.Viewport', {
            layout: 'fit',
            items: [
		display,
            ]
        });
        //var ws = new WebSocket("ws://colossus.gb.nrao.edu:8888/websocket");
        var ws = new WebSocket("ws://192.168.28.128:8888/websocket");
        ws.onopen = function() {
          //ws.send("Hello, world");
        };
        ws.onmessage = function (evt) {
            if (evt.data == 'close'){
                console.log('Closing WebSocket.');
                ws.close();
            } else {
                var data = eval(evt.data);
                me.getController('CanvasDisplay').updateDisplay(data[1]);
                console.log(data[0], data[1].length);
                ws.send(data[0]);
            }
        };
    }
});