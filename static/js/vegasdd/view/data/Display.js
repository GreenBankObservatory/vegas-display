Ext.define('vegasdd.view.data.Display', {
    extend: 'Ext.panel.Panel',
    alias: 'widget.display',
    bodyStyle: {
        background: '#fff',
    },

    initComponent: function() {
	this.spectralData = new Array();
	
	this.callParent(arguments);
    },
    
    initDrawComponent: function() {
	var me = this;
	this.width  = 800;
	this.height = 600;
	this.leftMargin = 50;
	this.top        = 50;
	var xlength     = this.width + this.leftMargin;
	var ylength     = this.height + this.top;
	var l = this.leftMargin; //Short hand

	var ylabel = Ext.create('Ext.draw.Sprite',{
            type: 'text',
            text: '<- time',
	    x: this.leftMargin - 30,
	    y: this.height / 2.0,
	});
	ylabel.setAttributes({
	    rotate: {
		degrees: -90
	    }
	}, true);

	this.drawComponent = Ext.create('Ext.draw.Component', {
            height: this.height,
            width: this.width,
            items: [
                {
                    type: 'path',
                    stroke: 'black',
                    path: ['M' + l + ' ' + this.top, 'L' + l + ' ' + ylength
			 , 'M' + l + ' ' + this.top, 'L' + xlength + ' ' + this.top]
                },
		ylabel,
		{
		    type: 'text',
		    text: 'channels',
		    x: this.width / 2.0,
		    y: this.top - 10,
		},
            ]
        });
	this.drawPoints();
	return this.drawComponent;
    },

    addData: function(data){
	this.spectralData.unshift(data);
    },

    drawPoints: function(){
	var me          = this;
	if (this.spectralData.length > 0){
            var numChannels = this.spectralData[0].length;
	} else {
            var numChannels = 0;
	}
	var pointWidth  = this.width / numChannels;
	var pointHeight = 0.1 * this.height;
	var xStart      = this.leftMargin;
	var yStart      = this.top;
	var value;
	for(var i = 0; i < this.spectralData.length; i++){
	    for(var j = 0; j < numChannels; j++){
		value = this.spectralData[i][j];
		var point = Ext.create('Ext.draw.Sprite',
		    {
			type: 'rect',
			width: pointWidth,
			height: pointHeight,
			fill: me.getFillColor(value),
			x: xStart + (pointWidth * j),
			y: yStart + (pointHeight * i),
		    }
		);
		this.drawComponent.items.push(point);
	    }
	}
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