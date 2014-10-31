// This file defines a Display object, which is the main part of the
// client program.  It controls the content and position of the
// canvases.
//

// set waterfall lower spectrum plot position and width
$("#waterfall-spectrum")
    .css("top", $("#axis").position().top + $("#axis").height())
    .css("width", $("#axis").width());

// make the bank radio button choices a jquery-ui buttonset
$("#bank-choice").buttonset();
$( '#bank-choice > label').first().click();
$( '#subband-choice > input').prop("disabled", true);
$("#subband-choice").buttonset();

// highcharts display options objects
var globalChartOptions = {
    chart: { animation: false },
    credits: { enabled: false },
    tooltip: { enabled: false },
    plotOptions: {
        series: {
            marker: { enabled: false },
            animation: false,
            states: {
                hover: { enabled: false }
            }, 
            enableMouseTracking: false,
            lineWidth: 2
        },
        yAxis: {
            type: 'logarithmic'
        }
    }
};
Highcharts.setOptions(globalChartOptions);  // set global highcharts options

var waterfallSpecOptions =  {
    legend: { enabled: false },
    series: [ {name: 'amplitude' }],
    yAxis: {
        title: { text: null },
        labels: {
            formatter: function () {
                return this.value.toPrecision(2);
            }
        },
        type : 'logarithmic'
    },
    xAxis: {
        title: { text: "GHz" },
        labels: {
            formatter: function () {
                return this.value/1e9;
            }
        }
    }
};
$( "#waterfall-spectrum" ).highcharts( waterfallSpecOptions );

var bankSpecOptions =  {
    legend: { title: 'Subband', layout: 'vertical', verticalAlign: 'top', align: 'right' },
    series: [{name: '0'}, {name: '1'}, {name: '2'}, {name: '3'},
             {name: '4'}, {name: '5'}, {name: '6'}, {name: '7'}],
    yAxis: {
        title: { text: "counts" },
        labels: {
            formatter: function () {
                return this.value.toPrecision(2);
            }
        }
    },
    xAxis: {
        title: { text: "GHz" },
        labels: {
            formatter: function () {
                return this.value/1e9;
            }
        }
    }
};

function getMin(data) {
    Array.prototype.min = function () {
        return Math.min.apply(null, this);
    };
    return Math.min.apply(null, data);
}

function getMax(data) {
    Array.prototype.max = function () {
        return Math.max.apply(null, this);
    };
    return Math.max.apply(null, data);
}

function drawSpecUnderWaterfall( data ) {
    var wfspec = $( '#waterfall-spectrum' ).highcharts();
    wfspec.series[0].setData( data );
    wfspec.setTitle( {text: 'Spectrum'} );
    wfspec.redraw();
}

function drawTimeSeries( data ) {
    $("#timeseries").highcharts({
        legend: { enabled: false },
        title: { text: 'Time Series' },
        series: [ {name: 'amplitude',
                   data: data}],
        yAxis: {
            title: { text: null },
            labels: {
                formatter: function () {
                    return this.value.toPrecision(2);
                }
            }
        }
    });
}

function clearCanvas( id ) {
    var canvas = $( id )[0];
    canvas.width = canvas.width;
    canvas.height = canvas.height;
}

function getFillColor(value, colormin, colormax) {
    var colorIdx = Math.floor(((value - colormin) / (colormax - colormin)) * 255);
    return 'rgb(' + colorIdx + ',0,0)';
}


// parse the amplitudes out of the (frequency, amplitude) pairs in the array
function amplitudes( ampAndSkyFreq ) {
    var amps = [];
    // for each pair
    $.each(ampAndSkyFreq, function(idx, pair) {
        if (null === pair) {
            amps.push(null);
        } else {
            amps.push(pair[1]);
        }

    });
    return amps;
}

// when we want to switch to displaying a different bank we
// need to clear the plot and axes
function resetDisplay(primaryCanvas, secondaryCanvas) { // --------------------------------------- resetDisplay
    // clear each of the two plot canvases
    clearCanvas( primaryCanvas );
    clearCanvas( secondaryCanvas );

    // reset the canvas top positions
    $( primaryCanvas ).css( "top", "-350px" );
    $( secondaryCanvas ).css( "top", "150px" );
}

function startRequestingData(display) { // --------------------------------------- startRequestingData
    display.updateId = setInterval(function () {
        display.ws.send( 'data');
    }, 3*1000); // 1000 milliseconds == 1 second
    console.log( 'update id: ' + display.updateId); // debug
}

function drawLowerSpec(number, bank, data) {
    // maybe use arguments feature of js instead of dataA, dataB, etc.
    var specChart = $("#spectrum-" + number).highcharts();

    $.each(data[bank], function(index, subband) {
        specChart.series[index].setData( subband, redraw=false, animation=false );
    });

    specChart.setTitle({text: 'Spectrometer ' + bank});
    specChart.redraw();
}

function updateNeighboringPlots( display, x, y ) {
    // Convert the (x, y) position for the mouse click to the (column, row)
    var column   = Math.floor( x / display.pointWidth  );
    var row      = Math.floor( y / display.pointHeight );
    console.log('row ' + row + ' column ' + column); 
    // If we clicked where there is data plot, tell the spectra plot
    // to display that data.  Otherwise, we clear the plot.
    if ( (row >= 0) && (row < display.waterfallSpectra.length) ) {
        drawSpecUnderWaterfall( display.waterfallSpectra[row] );
    } else {
        drawSpecUnderWaterfall( null );
    }

    // is the column between 0 and (e.g.) 512?
    if ( (column >= 0) && (column < display.waterfallSpectra[0].length) ) {

        // create a time series array, initialized to null we want it
        // to be the size of a full column so null values near the
        // bottom of a waterfall will be included in the plot
        var timeSeries = new Array( display.nSpectra );
        $.each(timeSeries, function(idx) {timeSeries[idx] = null;});

        // set values only for the number of spectra displayed in selected channel
        for (var jj = 0; jj < display.waterfallSpectra.length; jj++ ) {
            if (null !== display.waterfallSpectra[ jj ]) {
                timeSeries[jj] = display.waterfallSpectra[ jj ][ column ];
            }
        }

        console.log( 'updating time series, length', timeSeries.length );
        var tsAmps = amplitudes( timeSeries );
        drawTimeSeries( tsAmps );
    } else {
        drawTimeSeries( null );
    }

}

function Display() {
    this.nSpectra = 100; // number of spectra in waterfall plot
    this.canvasWidth = $("#axis").width(); // canvas width, in pixels
    this.canvasHeight = $("#axis").height(); // canvas height, in pixels
    this.waterfallBank = null;
    this.waterfallSpectra = new Array( this.nSpectra );
    for (var ii = 0; ii < this.waterfallSpectra.length; ii++) {
        this.waterfallSpectra[ii] = null;
    }
    this.pointHeight = this.canvasHeight / this.nSpectra; // datapoint height
    this.pointWidth = undefined; // defined later
    this.rowCounter = 0; // keeps track of the current row position
    this.primaryCanvas = "#waterfallA"; // switch as each canvas slides below the viewable area
    this.secondaryCanvas = "#waterfallB";
    this.updateId = null; // used to control update interval
    this.waterfallSubband = 0; // initialize subband to 0
    // position of the crosshairs, used to determine what is
    // displayed in the neighboring time series and spectrum plots
    this.crosshairX = 1; // default to channel 0
    this.crosshairY = 0; // default to most recent spectrum

    // initialize plots
    for (var number in [0,1,2,3,4,5,6,7]) {
        $( "#spectrum-" + number).highcharts( bankSpecOptions );
    }

    
    // Set listeners and associated event handlers.
    var me = this; // convention for local use of self
    this.initListeners = function () {
        $( '#reset-crosshairs' ).click( function ( e ) {
            var canvas = $( "#axis" )[0];
            var context = canvas.getContext( "2d" );

            me.crosshairX = 1;
            me.crosshairY = 0;

            clearCanvas( "#axis" );

            // display the position with text above the plot
            $( '#crosshair-position' ).html( "Column " + (me.crosshairX) + ", Row " + (me.crosshairY));
            updateNeighboringPlots( me, me.crosshairX, me.crosshairY );
        });

        // Registering click event for the plot.
        // On click, get the position of the click and draw cross
        // hairs to highlight the row and column clicked.  Then update
        // the timeseries and spectral plots to show the selected row
        // and column (channel).
        $( '#axis' ).click(function (e) {
            var canvas = $( "#axis" )[0];
            var context = canvas.getContext( "2d" );

            // get click pos relative to left edge of plot
            // http://api.jquery.com/event.pageX/
            me.crosshairX = Math.floor( e.pageX - $( "#axis" ).offset().left );

            // get click pos relative to top of plot
            // http://api.jquery.com/event.pageY/
            me.crosshairY = Math.floor( e.pageY - $( "#axis" ).offset().top );

            clearCanvas( "#axis" );

            // draw crosshairs
            context.beginPath();
            context.moveTo( me.crosshairX - 1, 0 );
            context.lineTo( me.crosshairX - 1, me.canvasHeight );
            context.moveTo( 0, me.crosshairY - 1 );
            context.lineTo( me.canvasWidth, me.crosshairY - 1 );
            context.strokeStyle = 'yellow'; // make the crosshairs red
            context.stroke();

            // display the position with text above the plot
            $( '#crosshair-position' ).html( "Column " + ( me.crosshairX ) + ", Row " + ( me.crosshairY ) );
            updateNeighboringPlots( me, me.crosshairX, me.crosshairY );
            });

        $( '#bank-choice' ).change(function () {
            // stop requesting data
            clearTimeout(me.updateId);

            // clear neighboring plots
            drawSpecUnderWaterfall( null );
            drawTimeSeries( null );

            // clear the plot display
            resetDisplay(me.primaryCanvas, me.secondaryCanvas);
            me.rowCounter = 0;

            me.waterfallBank = $( '#bank-choice').find( ':checked').val();
            console.info("----------------- Changed to bank " + me.waterfallBank);

            // hide subband buttons
            $( '#subband-choice > input').prop("disabled", true);

            // request data every 1 second for new bank
            startRequestingData(me);
        });

        $( '#subband-choice' ).change(function () {
            // stop requesting data
            clearTimeout( me.updateId );

            // clear neighboring plots
            drawSpecUnderWaterfall( null );
            drawTimeSeries( null );

            // clear the plot display
            resetDisplay(me.primaryCanvas, me.secondaryCanvas);
            me.rowCounter = 0;

            me.waterfallSubband = $( '#subband-choice' ).find( ':checked' ).val();
            console.info( "----------------- Changed to subband " + me.waterfallSubband );

            // request data every 1 second for new bank
            startRequestingData(me);
        });

    }; // +++++++++++++++++++++++++++ end of initListeners

    this.addData = function( data ) {
        // If we have reached the max amount of data to keep in
        // the buffer, pop off the end.
        if (this.waterfallSpectra.length >= this.nSpectra) {
            this.waterfallSpectra.pop();
        }

        // If we have plotted the max amount of data, swap the
        // canvases and reset the count.
        if (this.rowCounter >= this.nSpectra) {
            console.log("= " + this.rowCounter + " " + this.nSpectra);

            // Also, if we've been plotting on the second cavnas,
            // clear the secondary before the swap.
            $(this.secondaryCanvas).css("top", "-350px");
            clearCanvas(this.secondaryCanvas);
            var temp = this.primaryCanvas;
            this.primaryCanvas = this.secondaryCanvas;
            this.secondaryCanvas = temp;
            this.rowCounter = 0;
        } else {
            console.log( 'used ' + this.rowCounter + " of " + this.nSpectra + " available rows in plot");
        }

        // Finally, insert the new data to the beginning of the
        // buffer.
        this.waterfallSpectra.unshift( data );
    };

    this.drawDisplay = function (data, colormin, colormax) {
        // First a few words about how the waterfall plot is done.
        // In order to avoid redrawing every rectangle each time
        // we get a new sample, I'm stacking each sample on top of
        // the previous ones and moving the canvas down.  That way
        // we only plot the latest sample (row).  We keep track of
        // how many rows we have plotted and use it to find the
        // new position for the canvas.  Now, there are actually 3
        // total canvases we draw on.  One for the axis and two
        // for the waterfall.  There are two for the waterfall so
        // we can continuiously plot the data.  When the primary
        // canvas fills up, we swap it with the secondary one.
        var canvas = $(this.primaryCanvas)[0];
        var canvas2 = $(this.secondaryCanvas)[0];
        var context = canvas.getContext("2d");
        var context2 = canvas2.getContext("2d");

        // Given the number of rows we have plotted, what should the position be?
        this.rowCounter += 1;

        // Set the canvases top position accordingly.
        $(this.primaryCanvas).css("top", $(this.primaryCanvas).position().top + this.pointHeight);
        $(this.secondaryCanvas).css("top", $(this.secondaryCanvas).position().top + this.pointHeight);
        console.log("height " + this.pointHeight);
        console.log("canvas 1 top " + $(this.primaryCanvas).position().top);
        console.log("canvas 2 top " + $(this.secondaryCanvas).position().top);

        // Draw the new spectrum as rectangles
        for (var chan = 0; chan < data.length; chan++) {
            context.fillStyle = getFillColor(Math.log(data[chan]), colormin, colormax);
            context.fillRect(this.pointWidth * chan,
                             this.canvasHeight - (this.pointHeight * this.rowCounter),
                             this.pointWidth, this.pointHeight);
        }

        // Clip the bottom of the secondary canvas
        var clipPos = Math.round(canvas2.height - (this.pointHeight * this.rowCounter));
        context2.clearRect(0, clipPos, this.canvasWidth, (this.pointHeight * this.rowCounter));
    };

    this.initListeners(); // initialize event listeners


}  // +++++++++++++++++++++++++++++++++++++++++  end of Display function


// ------------------------------------- methods defined above

// instantiate a Display object
var rtd = new Display();

// Open the web socket to the data source, which is the tornado server that
// that is reading from the streaming manager(s)
var hostname = $("#hostname").html();
var port = $("#port").html();
rtd.ws = new WebSocket("ws://" + hostname + ":" + port + "/websocket");

rtd.ws.onopen = function (event) {
    rtd.ws.send( 'active_banks'); // request a list of active banks
};

rtd.ws.onclose = function (event) {
    clearTimeout(rtd.updateId);
    console.info( 'web socket closed');
    $( '#status')
        .html( 'No display connection.  Try refresh.')
        .css( 'color', 'red');
};

rtd.ws.onerror = function (event) {
    clearTimeout(rtd.updateId);
    console.error( 'web socket error');
    $( '#status')
        .html( 'Unknown error.  Try refresh.')
        .css( 'color', 'red');
};

// Handle data sent from the write_message server code in vdd_stream_socket.py
rtd.ws.onmessage = function (evt) {
    var msg = JSON.parse(evt.data);
    console.log( msg.header );

    switch(msg.header) {
    case "bank_config":
        // set the radio button properties depending on what banks
        // are available
        var bankArray = msg.body;
        $.each(bankArray, function (idx, bank) { console.log( 'enabling bank', bank ); });

        rtd.waterfallBank = bankArray[0];
        $( '#header').html( 'Spec ' + rtd.waterfallBank + ', SB ' + rtd.waterfallSubband);

        // send msg to server with default bank to display
        // request data every 1 second
        startRequestingData(rtd);
        break;
    case "data":

        // create a mapping of bank names to index numbers
        var Banknum = {'A':0, 'B':1, 'C':2, 'D':3, 'E':4, 'F':5, 'G':6, 'H':7};
        var md = msg.body.metadata;
        var spectra = msg.body.spectra;

        // display some metadata on screen
        $( '#header').html(   'Spec '        + rtd.waterfallBank + ', ' +
                              'Band '        + rtd.waterfallSubband);
        $( '#metadata').html( 'Project id: ' + md.project + ', ' +
                              'Scan: '       + md.scan + ', ' +
                              'Int: '        + md.integration);

        // set the first and last channel of every spectrum to null
        // this avoids displaying a common huge spike in the first channel
        var nullEdges = function(subband, idx, arr) {
            var firstChan = 0;
            var lastChan = subband.length - 1;
            var amplitudeIndex = 1; // freq. element is 0 (freq, amplitude)
            subband[ firstChan ][ amplitudeIndex ] = null;
            subband[ lastChan  ][ amplitudeIndex ] = null;
        };
        $.each(spectra, function(bank) {
            if (spectra[ bank ].length > 0) {
                // for each subband on this bank
                spectra[ bank ].forEach( nullEdges );
            }
        });
        
        // for each subband of the bank in the waterfall display
        //  disable the buttons of subbands that are not currently
        //  being used by VEGAS
        spectra[ rtd.waterfallBank ].forEach(function( subband, index, array ) {
            var selectorString = '#subband-choice > input:eq(' + index + ')';
            $( selectorString ).prop( "disabled", false );
        });
        // update the buttons
        $( "#subband-choice" ).buttonset( "refresh" );
        $( '#subband-choice > label' )[ rtd.waterfallSubband ].click();

        // if we are updating the waterfall display
        if ( md.update_waterfall == 1 )
            {
                try {                    
                    var amps = amplitudes( spectra[rtd.waterfallBank][rtd.waterfallSubband] );
                    rtd.pointWidth = rtd.canvasWidth / amps.length;
                    rtd.addData(spectra[rtd.waterfallBank][rtd.waterfallSubband].slice(1,-1));
                    var colormin = Math.log( getMin( amps.slice(1,-1) ) ); // omit first and last channels
                    var colormax = Math.log( getMax( amps.slice(1,-1) ) );
                    rtd.drawDisplay(amps, colormin, colormax, rtd.pointWidth);
                    updateNeighboringPlots(rtd, rtd.crosshairX, rtd.crosshairY);
                    $( '#status' )
                        .html( 'Running' )
                        .css( 'color', 'green' );
                    $( "#timestamp" ).html( new Date().toTimeString() );

                } catch(err) { console.error( 'ERROR', err ); }

            }
        else
            {
                $( '#status' )
                    .html( 'Waiting for data' )
                    .css( 'color', 'orange' );
            }
        
        // draw the spec plots for all banks and subbands
        $.each(Banknum, function(bb, banknum) {
            var bankSelect = '#bank-choice > input:eq(' + banknum + ')';
            var bankTextSelect = "#bank-choice > label:eq(" + banknum + ") span";
            var bankdata = spectra[bb];

            if ( bankdata.length > 0 ) {
                $( bankSelect ).prop( "disabled", false );
                $( bankTextSelect ).css({color: "green"});
            } else {
                $( bankTextSelect ).css({color: "grey"});          
            }
            drawLowerSpec((banknum).toString(), bb, spectra);
        });
        break;
    default:
        console.error( 'Not updating for message:', msg.header );
        break;
    }

};
