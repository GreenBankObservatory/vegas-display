Ext.define('vegasdd.controller.Display', {
    extend: 'Ext.app.Controller',
    views: [
	'data.Display',
    ],

    init: function() {
        console.log('Initialized Display! This happens before the Application launch function is called');
    },

    setDisplay: function(display){
	this.display = display;
	var dc = this.display.initDrawComponent();
	this.display.add(dc);
	this.display.doLayout();
    },

    updateDisplay: function(data){
	this.display.removeAll(true);
	this.display.addData(data);
	var dc = this.display.initDrawComponent();
	this.display.add(dc);
	this.display.doLayout();
    },
});