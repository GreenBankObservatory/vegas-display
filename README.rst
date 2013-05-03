The VEGAS Data Display
======================

**What is it?**

The VEGAS Data Display (VDD) is a real-time data display for the Versatile GBT 
Astronomical Spectrometer (VEGAS).  It provides features similar to what is 
those of the GBT FITS Monitor (GFM), but with added capabilities.  It does not 
replace GFM, which is still required for other backends.

The VDD is both a monitoring tool for observers and operators 
as well as a debugging tool for engineers.  It interfaces with VEGAS through 
the data 
streaming software infrastructure.

**Why do we have it?**

You might be thinking: why make another data display if we already have GFM?

First of all, GFM is not capable of displaying data from the many possible 
spectral windows provided by VEGAS.

GFM, in spectral line mode, is capable of displaying spectra from a maximum of 
8 spectral windows of the GBT spectrometer.  It consists of a 2d display of 
frequency/channel vs power spectral density.  With VEGAS, it must be possible 
to display 8 of a possible 64 spectral windows (a.k.a. subbands).

In addition, the VDD specification requires a waterfall plot (3d plot) to 
display a dynamic spectrum.  The waterfall plot provides a look-back capability 
useful for identifying features over time.

Also, the VDD must have the ability to filter on other monitoring parameters 
not provided by GFM.

Finally, the VDD was deemed to be a good small-project opportunity to test 
features of the GBT data streaming infrastructure and a web 
application UI instead of more typical GB desktop GUIs.

In summary, here are the differences between GFM and VDD:

========================   ==================================    ===================
Feature                    GFM                                   VDD
========================   ==================================    ===================
displayable windows        up to 8 (of 8)                        up to 8 (of 64)
granularity                scan                                  integration
plot history               single scan                           >= 10 mins
time series                no                                    yes
interactive                yes                                   yes
obs. types                 pointing, continuum, spectral line    spectral line
application type           desktop                               web
input                      FITS files                            data stream
========================   ==================================    ===================

**Where can you find it?**

Because this is a web application, you can use the display in a web browser.
The VDD was designed to work across a variety of browsers but it has only been 
fully tested on Firefox.

The URL is:  http://www.nrao.edu/gb/vdd

**How do I use it?**

Read more of this documentation and use help available within the application 
window.

**More about that waterfall plot**

The waterfall plot is interactive.  For example, a crosshair can be moved 
around on the 3d 
plot, to select 2d 'cuts' of the spectrum at a given time and time series of a 
single channel.

At any instance, a single 3d plot or 8 3d plots can be displayed. If all 
8 spectrometers are configured in single subband mode, then the eight 3d 
plots can be the data from the 8 banks.

On the other hand if the spectrometers 
are configured in 8 subband mode, then the eight 3D plots can be data from the 
8 sub-bands of a banks or data from a selected subset of 8 out of the 64 
sub-bands. 

For mixed configuration (ie some banks in single subband and others 
in 8 subband mode), the rule for the display is that the user selects up to 
a maximum of 8 subbands from all the available subands. 

The VDD displays every integration when the integration time is greater than 1 
second.  For observations with sub-second integrations, the display will show 
the last available integration at 1 second intervals.

The dynamic spectrum displayis data with a history of at least 10 minutes.


