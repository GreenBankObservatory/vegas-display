Ext.define('vegasdd.view.data.CanvasDisplay', {
    extend: 'Ext.panel.Panel',
    alias: 'widget.canvasdisplay',
    bodyStyle: {
        background: '#fff',
    },

    initComponent: function() {
	var me = this;
	this.width  = 800;
	this.height = 600;
	this.vertMargin  = 50;
	this.hortMargin = 50;
        this.heightScale = .01;
	var cwidth      = this.width + this.hortMargin;
	var cheight     = this.height + this.vertMargin;
        this.items = [{
	        xtype: "panel",
                html: "<canvas id='bg' width='" + cwidth + "' height='" + cheight + "' style='z-index: 10; border:1px solid #000000;'></canvas><canvas id='fg' width='" + this.width + "'height='" + this.height + "' style='z-index: 11'></canvas>"
	}];

	this.addListener('render', this.drawAxis);
	this.callParent(arguments);
    },

    clearCanvas: function(){
        var c = document.getElementById("fg");
        var ctx = c.getContext("2d");
        ctx.clearRect(0, 0, this.width, this.height);
    },        
            
    drawDisplay: function(spectralData){
        var c = document.getElementById("fg");
        var ctx = c.getContext("2d");

        var me = this;
        var numChannels = spectralData[0].length;
	var pointWidth  = (this.width - this.vertMargin) / numChannels;
	var pointHeight = this.heightScale * (this.height - this.hortMargin);
	var xStart      = this.hortMargin;
	var yStart      = this.vertMargin;
	var value;
	for(var i = 0; i < spectralData.length; i++){
	    for(var j = 0; j < numChannels; j++){
		value = spectralData[i][j];
		ctx.fillStyle = this.getFillColor(value);
		ctx.fillRect(xStart + (pointWidth * j),
			     yStart + (pointHeight * i),
			     pointWidth,
			     pointHeight)
	    }
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

});