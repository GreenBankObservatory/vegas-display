Ext.define('vegasdd.controller.CanvasDisplay', {
    extend: 'Ext.app.Controller',
    views: [
	'data.CanvasDisplay',
    ],

    init: function() {
        this.spectralData = new Array();
    },

    setDisplay: function(display){
	this.display = display;
    },

    addData: function(data){
	var maxSize = 1 / this.display.heightScale;
	if (this.spectralData.length >= maxSize){
	    this.spectralData = new Array();
            this.display.clearCanvas();
            //this.display.drawAxis();
	}
	this.spectralData.unshift(data);
    },

    updateDisplay: function(data){
	this.addData(data);
	this.display.drawDisplay(this.spectralData);
    },
});