Ext.define('vegasdd.view.data.Point', {
    extend: 'Ext.draw.Sprite',
    alias: 'widget.point',
    constructor: function() {
        // map color names to hex values
        this.colors = { red:  '#FF0000',
                        green: '#00FF00',
                        blue: '#0000FF',
                        purple: '#800080',
                        yellow: '#FFFF00',
                        orange: '#FFA500',
                      };

        var parentConfig = {
            type: 'rect',
            fill: 'red',
            stroke: 2,
            width: 45,
            height: 10,
            x: 100,
            y: 100,
        };
        this.callParent([parentConfig]);
    },

    setData: function(){
    },
});