// This file defines a Display object, which is the main part of the
// client program.  It controls the content and position of the
// canvases.
//

// highcharts display options objects
var globalChartOptions = {
    chart: { animation: false,
	     borderColor: 'black',
	     borderWidth: 1,
	     marginRight: 35
	   },
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
            lineWidth: 1
        },
    },
    yAxis: {
	// type: 'logarithmic',
	// minorTickInterval: 'auto',
	tickPixelInterval: 10,
	startOnTick: false,
	endOnTick: false,
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
        },
	tickPixelInterval: 50
    },
    legend: { enabled: false, title: 'Subband', layout: 'vertical',
	      verticalAlign: 'top', align: 'right' },
    title: { text: null }
};
Highcharts.setOptions(globalChartOptions);  // set global highcharts options

var bankSpecOptions =  {
    series: [{name: '0'}, {name: '1'}, {name: '2'}, {name: '3'},
             {name: '4'}, {name: '5'}, {name: '6'}, {name: '7'}],
};

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

function drawSpec(number, bank, data) {
    // maybe use arguments feature of js instead of dataA, dataB, etc.
    var specChart = $("#spectrum-" + number).highcharts();

    if (data !== null) {
	$.each(data[bank], function(index, subband) {
            specChart.series[index].setData( subband, redraw=false, animation=false );
	});

    }
    specChart.setTitle({text: bank, align: 'left'});
    specChart.redraw();
}

// ----------------------------------------------------------------------

// Open the web socket to the data source, which is the tornado server that
// that is reading from the streaming manager(s)
var hostname = $("#hostname").html();
var port = $("#port").html();
var ws = new WebSocket("ws://" + hostname + ":" + port + "/websocket");

$( "#timestamp" ).html( new Date().toDateString() + ',\n' +
			new Date().toTimeString() );
for (var number in [0,1,2,3,4,5,6,7]) {
    $( "#spectrum-" + number).highcharts( bankSpecOptions );
}

ws.onclose = function (event) {
    console.info( 'web socket closed');
    $( '#status')
        .html( 'No display connection.  Try refresh.')
        .css( 'color', 'red');
};

ws.onerror = function (event) {
    console.error( 'web socket error');
    $( '#status')
        .html( 'Unknown error.  Try refresh.')
        .css( 'color', 'red');
};

// Handle data sent from the write_message server code in vdd_stream_socket.py
ws.onmessage = function (evt) {
    var msg = JSON.parse(evt.data);
    switch(msg.header) {
    case "data":

        // create a mapping of bank names to index numbers
        var Banknum = {'A':0, 'B':1, 'C':2, 'D':3, 'E':4, 'F':5, 'G':6, 'H':7};
        var md = msg.body.metadata;
        
        // if we are updating the waterfall display
        if ( md.update == 0 )
            {
                $( '#status' )
                    .html( 'Waiting for data' )
                    .css( 'color', 'orange' );
		spectra = null;
            }
        else
            {
                $( '#status' )
                    .html( 'Running' )
                    .css( 'color', 'green' );
                $( "#timestamp" ).html( new Date().toDateString() + ',\n' +
					new Date().toTimeString() );

		var spectra = msg.body.spectra;

		// display some metadata on screen
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

		// draw the spec plots for all banks and subbands
		$.each(Banknum, function(bb, banknum) {
		    drawSpec((banknum).toString(), bb, spectra);
		});
            }

        
        break;
    default:
        console.error( 'Not updating plot. Message is:', msg.header );
        break;
    }

};
