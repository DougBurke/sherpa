************************
Plotting backend details
************************

.. warning::
   The plotting backend API is currently re-designed and details might change in the near future.

Plotting in Sherpa is done through *plotting backends*. A *backend* is an
external package that performs the actual plotting function, i.e. it creates a
canvas and puts color on paper or on the screen. The Sherpa plotting classes are
written in a backend-independent way; they work with any plotting backend that
is supported by Sherpa. We also use the term *backend* to refer to Sherpa
classes that connect the Sherpy plot objects with the plotting backend by
translating Sherpa options into backend-specific commands. The details of that
are explained below, but, in short, a backend class would translate the sherpa
backend-independent "plot a line in red from here to there" into backend
specific ``plt.plot(x,y, linecolor='r')`` (if the backend is :term:`matplotlib`).

Instead of utilizing Sherpa classes and commands to plot data, users can
alternatively just access the data in the Sherpa data objects (e.g. the x and y
values of a dataset) and perform plotting operations directly with any plotting
backend that is available ot them. This method may be less convenient, but it
works for ploting backends not (yet) supported by Sherpa.

Backend-independent plotting options
====================================

Sherpa defines a number of plotting options that can be used with any backend,
thus code that limits itself to those options can run independent of which
backend is set up in Sherpa. All default settings and most examples use only
backend-inpdependent plotting options. The resulting plots will not look
identical in each backend, e.g. thickness of a line or the font type of an
annotation might differ, but they will convey the same information. For example,
"a blue dotted line" will generally appear blue and dotted, even though the
shade of blue or the size of the dots might differ between plotting backends. 

In some cases, a plotting backend might not support all Sherpa plot options (for
example, a plotting backend might not have a command to change the line style).
In those rare cases, a setting might be ignored; but a setting from Sherpa's
list of backend independent value will never raise an error.

The names of plotting options and values that all Sherpa plotting backends
accept are chosen to match common :term:`matplotlib` settings which are familiar
to many scientific Python users, and to maintain backwards compatibility with
previous version of Sherpa. They offer limited choices, but those are sufficient
for most plots. For example, only few different line styles are specified, but
in practice, most plots can be done with just solild, dashed, and maybe dotted
lines.

The following settings are accepted for all Sherpa plotting backends:

Colors
------

Colors are used for the color of lines, symbols, errorbars etc.

- ``'b'`` (blue)
- ``'r'`` (red)
- ``'g'`` (green)
- ``'k'`` (black)
- ``'w'`` (white), 
- ``'c'`` (cyan)
- ``'y'`` (yellow)
- ``'m``` (magenta)
- ``None`` (ploting backend default)

Line styles
------------

Because of legacy from both Chips and :term:`matplotlib` backends, line styles
can be specified in more than one form:

- ``'noline'`` or  ``''`` (empty string) or ``'None'`` (as a string)
  means that no line shall be plotted.
- ``'solid'`` or ``'-'``  for solid lines,
- `None`  for the default style - usually a solid line, too,
- ``'dot'`` or ``':'`` for dotted lines,
- ``'dash'`` or ``'--'`` (dashed) for dashed lines, and
- ``'dotdash'`` or ``'-.'`` for a dot-dashed line.

Markers
--------
- ``"None"`` as a string or ``""`` (empty string) means that no marker will be
  shown, 
- ``"."`` shows dots,
-  ``"o"`` shows cicles (filled or unfilled depending on the backend), 
- ``"+"`` shows plus signs, 
- ``"s"`` shows squares.

Additional backend-specific settings
====================================

Most plotting backends accept more than just the backend-independent options
listed above. For example, :term:`matplotlib` allows `many different ways to
specify colors to cover the entire RGB range
<https://matplotlib.org/stable/tutorials/colors/colors.html>`_, such as
``color=(.3, .4, .5, .2)`` or ``color='xkcd:eggshell'``. The Sherpa plotting
methods will pass any value to the underlying backend, but only the options in
the backend independent list are guaranteed to work in every case. For example, 

  >>> from sherpa.data import Data1D
  >>> from sherpa.plot import DataPlot
  >>> d = Data1D('example data', [1, 2, 3], [3, 2, 5])
  >>> dplot = DataPlot()
  >>> dplot.prepare(d)
  >>> dplot.plot(markerfacecolor='xkcd:eggshell')

will succeed with the `~sherpa.plot.pylab_backend.PylabBackend`, but raise an
error if the active backend is `~sherpa.plot.bokeh_backend.BokehBackend`. In
contrast, ``color='k'`` is also not understood by bokeh natively, but because it is on
the backend-independent list, Sherpa will translate ``'k'`` to a form that bokeh
does understand (``'black'`` in this case).

Backends may also accept additional keywords to specify more plotting properties
such as the transparancy of an element or an URL that is opened when clicking on
an element. Those can simply be passed to the Sherpa plotting command, which
will pass them through to the plotting backend:

  >>> from sherpa.data import Data1D
  >>> from sherpa.plot import DataPlot
  >>> d = Data1D('example data', [1, 2, 3], [3, 2, 5])
  >>> dplot = DataPlot()
  >>> dplot.prepare(d)
  >>> dplot.plot(url='https://www.example.com')

Since Sherpa does not process those options itself, but just passes them on to
the underlying backend module, they are not documented here - see the
documenation of the specific plotting module for details. Also, they will fail and
raise an error if the plotting backend in use doesn ot understand the ``url`` keyword.

In some cases, the Sherpa plotting commands create several visualization
elements at the same time (lines, symbols, error bars, axes, labels). This makes
using Sherpa classes convenient, but it also means that the plotting functions
do not offer options to customize each and every part. In general, the plotting
functions pass color, linestyle etc. to the elements that describes the data
(line, marker) and generate labels or axes grids using default settings. Backend
specific code can be used to change the properties of the current figure after
the Sherpa plotting.

Backend interface
=================

.. note::

   This section is mostly relevant for developers or advanced users who write new
   Sherpa plot classes or new backends.

This section describes the API that all Sherpa backends offer to explain how to
use it and why it was designed this way. See `sherpa.plot.backend.BaseBackend`
for a complete listing of the calling signature for each function. 
The `sherpa.plot.backend.BasicBackend` backend extends 
``sherpa.plot.backend.BaseBackend` by raising a warning message for 
plotting functions (plot, image, histrogram etc.) that are not implemented.
It is a the base for any real functional backend, which will override those
methods, but offer useful user feedback for any method not provided.
This future-proofs any backend derived from this class: When sherpa adds new
functions to its backend definition, they will be added here with a warning
message. Thus, any backend derived from this class will always provide the
interface that sherpa requires from a plotting backend.


Plotting functions
------------------

Each backend shall support the plotting functions listed below, where "support"
means "has to provide these functions and accept a standard list of arguments
without crashing or raising an exception". We explicitly allow for backends that
implement some of these as a no-op, e.g. because the underlying plotting library
does not support 2D data. In that case, the backend would typically issue a
warning.

The plotting functions are not separated by "how things look on paper" (thus "plot" is
a long method that is responsible for points, lines, and errorbars), but
by "what is the input data type":

- `~sherpa.plot.backend.BaseBackend.plot` (for scatter plots with markerstyle
  set, for line plots with linestyle set, and for errorbars with ``xerr`` or
  ``yerr`` set to `True`); accepts (x, y) data with optional error bars in each
  dimension. Data can be scalar (for a single marker), or array-like.
- `~sherpa.plot.backend.BaseBackend.histo` (similar to plot, but with
  "histogram-style" lines); accepts (xlo, xhi, y) data with optional xerr, yerr.
- `~sherpa.plot.backend.BaseBackend.contour` for (x0, x1, z) data
- `~sherpa.plot.backend.BaseBackend.image` for (x0, x1, z) data on a regular
  grid. An image is different from a contour in the sense that an image is
  pixelated on a regular grid, while a contour can in principle describe a
  continuous quantity or an irregular grid, even if the current implementation
  may not provide that flexibility.

Annotations
-----------

Backends should also implement the follwing annotation functions. They do not
depend on the data plotted, but just annotate the plot, e.g. a
`~sherpa.plot.RatioPlot` shows the ratio betwen data and model and can use an
annotation to mark the ``ratio=1`` line.

- `~sherpa.plot.backend.BaseBackend.hline` (horizontal across the entire axes)
- `~sherpa.plot.backend.BaseBackend.vline` (vertical across the entire axes)

Other annotations (e.g. text labels) might be added to the API in the future.
For this reason new backends should inherit from
`~sherpa.plot.backend.BasicBackend`. Any function added to the API will be
implemented in `~sherpa.plot.backend.BasicBackend` as a no-op with a
warning to the user like "Feature XYZ is not available in your backend ". That
way, all Shepa plots can immediately make use of newly added functions without
breaking existing plotting backends; the worst that happens is that not all
annotation will be visible in every backend.

Return values
-------------

Sherpa does not expect a specific return argument from any plotting function,
but they are allowed to have return values if that is helpful for their internal
implementation, e.g. in the matplotlib backend, plotting a line might return a
line object so that error bars plotted later can use ``line.color`` to match the
color of that line.

Creating plots and panels, clearing and overplotting
----------------------------------------------------
At this stage, we keep the existing API for creating plot and panels, for
clearing and overplotting, i.e. each of the plotting functions above accepts
 the following arguments: title, xlabel, ylabel, xlog, ylog, overplot, clearwindow

Multi-panels plot can be set with clear_window, set_subplot, set_jointplot
[copy documentation from CAIO 4.14 pylab_backend.clear_window etc. into here because that describes use and function]

Interaction with interactive plots in the UI
--------------------------------------------
Each backend has additional functions that are called before, during and after
interactive plots (begin, exception, and end), and for the setup of 
multi-panel plots [those are taken essentially unchanged from the 4.14 version, so can copy from code into specs]

Other methods
--------------

Backends need to have a few methods

- ``as_html_XXX`` (where XXX is a plot type) that are used for interactive
  display in the notebook with ``_repr_html_``.  These functions take a plot
  object and return an html representation as a string.
- ``get_XXX_plot/hist_prefs`` (where XXX is a plot type) which returns a
  dictionary of preferences that is used for displaying this plot.
- `~sherpa.plot.backend.BasicBackend.get_latex_for_string` to format latex in strings.


Example
-------

Testing
--------