#
#  Copyright (C) 2007, 2015, 2020, 2021, 2022
#  Smithsonian Astrophysical Observatory
#
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
import logging

from sherpa.utils import get_keyword_defaults
from sherpa.utils import formatting


__all__ = ('BasicBackend')


lgr = logging.getLogger(__name__)
warning = lgr.warning


class BasicBackend():
    '''A dummy backend for plotting.

    This backend implements only minimal functionality (some formatting of
    strings as HTML or LaTeX which are usually used as axis labels), but no
    real plotting capabilities. It is here to ensure that the `sherpa.plot`
    module can be imported, even if no plotting backend is installed.

    In this sense, this backend can be understood as the "base" for backends.
    The string-formatting is implemented here so that other backends don't
    have to dublicate that; they can call the functions here.
    '''
    def setup_plot(self, axes, title, xlabel, ylabel, xlog=False, ylog=False):
        """Basic plot setup.

        Parameters
        ----------
        axes
            The plot axes (output of setup_axes).
        title, xlabel, ylabel : str or None
            The plot, x-axis, and y-axis titles. They are skipped if
            the empty string or None.
        xlog , ylog : bool
            Should the scale be logarithmic (True) or linear (False)?

        """
        pass

    def set_subplot(row, col, nrows, ncols, clearaxes=True,
                    **kwargs):
        """ Select a plot space in a grid of plots or create new grid

        This method adds a new subplot in a grid of plots. 
 
        Parameters
        ----------
        row, col : int
            index (starting at 0) of a subplot in a grid of plots
        nrows, ncols : int
            Number of rows and column in the plot grid
        clearaxes : bool
            If True, clear entire plotting area before adding the new 
            subplot.

        Note
        ----
        This method is intended for grids of plots with the same number of 
        plots in each row and each column. In some backends, more
        complex layouts (e.g. one wide plot on row 1 and two smaller plots
        in row 2) might be possible.
        """
        pass

    def set_jointplot(row, col, nrows, ncols, create=True,
                    top=0, ratio=2):
        """Move to the plot, creating them if necessary.
        Parameters
        ----------
        row : int
            The row number, starting from 0.
        col : int
            The column number, starting from 0.
        nrows : int
            The number of rows.
        ncols : int
            The number of columns.
        create : bool, optional
            If True then create the plots
        top : int
            The row that is set to the ratio height, numbered from 0.
        ratio : float
            The ratio of the height of row number top to the other
            rows.
        """
        pass

    def clear_window():
        """Provide empty plot window
        
        Depending on te backend, this may provide a new,
        empty window or clear the existing, current window.
        """
        pass

    def initialize_plot(dataset, ids):
        """Create the plot window or figure for the given dataset.

        Parameters
        ----------
        dataset : str or int
        The dataset.
        ids : array_like
        The identifier array from the DataStack object.

        See Also
        --------
        select_plot

        """
        pass

    def select_plot(dataset, ids):
        """Select the plot window or figure for the given dataset.

        The plot for this dataset is assumed to have been created.

        Parameters
        ----------
        dataset : str or int
        The dataset.
        ids : array_like
        The identifier array from the DataStack object.

        See Also
        --------
        initialize_plot

        """
        pass

    def begin(self):
        '''Called from the UI before and interactive plot is started.
        '''
        pass

    def exceptions(self):
        '''Called from the UI if any exceptions occur during plotting.'''
        pass

    def end(self):
        '''Called from the UI after an interactivep lot is done'''
        pass

    def plot(self, x, y, *,
             xerr=None, yerr=None, 
             title=None, xlabel=None, ylabel=None,
             xlog=False, ylog=False,
             overplot=False, clearwindow=True,
             label=None,
             xerrorbars=False,
             yerrorbars=False,
             color=None,
             linestyle='solid',
             linewidth=None,
             drawstyle='default',  # HMG: Do we need this?
             marker='None',
             alpha=None,
             markerfacecolor=None,
             markersize=None,
             ecolor=None,
             capsize=None,
             xaxis=False,  # HMG: suggest to drop this
             ratioline=False,  # HMG suggest to drop this
             **kwargs):
        """Draw x,y data.
        
        This method combines a number of different ways to draw x/y data:
        - a line connecting the points
        - scatter plot of symbols
        - errorbars

        All three of them can be used together (symbols with errorbars
        connected by a line), but it is also possible to use only one or two
        of them. By default, a line is shown (``linestyle='solid'``), but marker
        and error bars are not (``marker='None'`` and ``xerrorbars=False``
        as well as ``yerrorbars=False``).

        Parameters
        ----------
        x : array-like or scalar number
            x values
        y : array-like or scalar number
            y values, same dimension as `x`.
        xerr, yerr: float or array-like, shape(N,) or shape(2, N), optional
            The errorbar sizes:
              - scalar: Symmetric +/- values for all data points.
              - shape(N,): Symmetric +/-values for each data point.
              - shape(2, N): Separate - and + values for each bar.
                First row contains the lower errors, 
                the second row contains the upper errors.
              - None: No errorbar.

             Note that all error arrays should have positive values.
        title : string, optional
            Plot title (can contain LaTeX formulas).
            Only used if a new plot is created.
        xlabel, ylabel : string, optional
            Axis labels (can contain LaTeX formulas).
            Only used if a new plot is created.
        xlog, ylog : bool
            Should x/y axes be logartihmic (default: linear)?
            Only used if a new plot is created.
        overplot : bool
            If `True`, the plot is added to an existing plot, if not
            (the default) a new plot is created.
        clearwindow : bool
            If `True` (the default) the entire figure area is cleared
            to make space for a new plot.
        xerrorbars, yerrorbars : bool
            Should x/y error bars be shown? If this is set to `True ` errorbars are
            shown, but only if the size of the errorbars is provided in the 
            `xerr`/`yerr` parameters. The purpose of having a separate switch
            `xerrorbars` is that the prepare method of a plot can create the errors
            and pass them to this method, but the user can still decide to change the
            style of the plot and choose if error bars should be displayed.
        color : string (some backend may accept other)
            The following colors are accepted by all backends:
            ``'b'`` (blue), ``'r'`` (red), ``'g'`` (green), ``'k'`` (black),
            ``'w'`` (white), ``'c'`` (cyan), ``'y'`` (yellow), ``'m``` (magenta)
            but they may not translate to the exact same RGB values in each backend,
            e.g. ``'b'`` could be a different shade of blue depending on the backend.

            Some backend might accept additional values.
        linestyle : string
            The following values are accepted by all backends:
            ``'noline'``, ``'solid'``, ``'dot'``, ``'dash'``, 
            ``'dotdash'``, ``'-'`` (solid line), ``':'`` (dotted),
            ``'--'`` (dashed), ``'-.'`` (dot-dashed), ``''`` (empty string,
            no line shown), `None` (default - usually solid line).

            Some backends may accept additional values.
        linewidth : float
            Thickness of the line.
        drawstyle : string
            DO WE NEED THIS IN BACKEND-INDEPENDENT INTERFACE?
        marker : string
            The following values are accepted by all backends:
            "None" (as a string, no marker shown), "." (dot), "o" (cicle), "+", "s" (square),
             "" (empty string, no marker shown)

            Some backends my accept additional values.

        alpha : float
            Number between 0 and 1, setting the transparency.
        markerfacecolor : string
            see `color`
        markersize : float, optional
            Size of a marker. The scale may also depend on the backend.
            None uses the backend-specific default.
        ecolor : string
            Color of the errorbars.
        capzise : float
            Size of the cap drawn at the end of the errorbars.
        """
        warning(f'{self.__class__} does not implement line/symbol plotting.' +
            'No plot will be produced.')

    def histo(self, xlo, xhi, y, *,
              yerr=None, 
              title=None, xlabel=None, ylabel=None,
              overplot=False, clearwindow=True,
              xlog=False, ylog=False,
              label=None,
              xerrorbars=False,
              yerrorbars=False,
              color=None,
              linestyle='solid',
              linewidth=None,
              drawstyle='default',
              marker='None',
              alpha=None,
              markerfacecolor=None,
              markersize=None,
              ecolor=None,
              capsize=None,
              barsabove=False,
              **kwargs):
        """Draw histogram data.

        The histogram is drawn as horizontal lines connecting the
        start and end points of each bin, with vertical lines connecting
        consecutive bins. Non-consecutive bins are drawn with a
        (Nan, NaN) between them so no line is drawn connecting them.

        Points are drawn at the middle of the bin, along with any
        error values.
        """
        warning(f'{self.__class__} does not implement histogram plotting.' +
                'No histogram will be produced.')

    def contour(self, x0, x1, y, 
                levels=None,
                title=None, xlabel=None, ylabel=None,
                overplot=False, clearwindow=True,
                xlog=False, ylog=False,
                label=None,
                color=None,
                linestyle='solid',
                linewidth=None,
                alpha=None,
                **kwargs):
        """Draw 2D contour data.

        """
        warning(f'{self.__class__} does not implement contour plotting.' +
                'No countour will be produced.')

    def image(self, x0, x1, y, *,
              extent=None,
              title=None, xlabel=None, ylabel=None,
              overplot=False, clearwindow=True,
              xlog=False, ylog=False,
              label=None,
              color=None,
              alpha=None,
              **kwargs):
        warning(f'{self.__class__} does not implement image plotting.' +
                'No image will be produced.')

    def vline(self, x, *,
              ymin=0, ymax=1,
              title=None, xlabel=None, ylabel=None,
              overplot=False, clearwindow=True,
              color=None,
              linestyle=None,
              linewidth=None,
              **kwargs):
        """Draw a vertical line"""
        warning(f'{self.__class__} does not implement line plotting.' +
                'No line will be produced.')

    def hline(self, y, *,
              xmin=0, xmax=1,
              title=None, xlabel=None, ylabel=None,
              overplot=False, clearwindow=True,
              color=None,
              linestyle=None,
              linewidth=None,
              **kwargs):
        """Draw a horizontal line"""
        warning(f'{self.__class__} does not implement line plotting.' + 
                'No line will be produced.')

    def get_latex_for_string(self, txt):
        """Convert LaTeX formula

        Parameters
        ----------
        txt : str
            The text component in LaTeX form (e.g. r'\alpha^2'). It
            should not contain any non-LaTeX content.

        Returns
        -------
        latex : str
            The txt modified as appropriate for a backend so that the LaTeX
            will be displayed properly.

        """
        return txt

    # HTML representation as tabular data
    #
    def as_html(self, data, fields):
        """Create HTML representation of a plot

        Parameters
        ----------
        data : Plot instance
            The plot object to display.
        fields : sequence of strings
            The fields of data to use.

        """

        # Would like a nicer way to set the summary label, but without
        # adding a per-class field for this it is safest just to use
        # the object name.

        meta = []
        for name in fields:
            # skip records which we don't know about. This indicates
            # an error in the calling code, but we don't want it to
            # stop the generation of the HTML.
            #
            try:
                val = getattr(data, name)
            except Exception as e:
                lgr.debug("Skipping field {}: {}".format(name, e))
                continue

            meta.append((name, val))

        ls = [formatting.html_section(meta, open_block=True,
                                    summary=type(data).__name__)]
        return formatting.html_from_sections(data, ls)

    # The follwowing methods will almost all be removed in Step 2
    def get_split_plot_defaults(self):
        return get_keyword_defaults(self.set_subplot, 3)


    def get_plot_defaults(self):
        return get_keyword_defaults(self.plot, 7)


    def get_point_defaults(self):
        return get_keyword_defaults(self.point, 2)


    def get_contour_defaults(self):
        return get_keyword_defaults(self.contour, 6)


    def get_histo_defaults(self):
        return get_keyword_defaults(self.histo, 6)


    def get_dummy_defaults(self):
        return {}


    get_data_plot_defaults = get_dummy_defaults
    get_model_plot_defaults = get_dummy_defaults
    get_fit_plot_defaults = get_dummy_defaults
    get_resid_plot_defaults = get_dummy_defaults
    get_ratio_plot_defaults = get_dummy_defaults

    get_data_contour_defaults = get_dummy_defaults
    get_model_contour_defaults = get_dummy_defaults
    get_fit_contour_defaults = get_dummy_defaults
    get_resid_contour_defaults = get_dummy_defaults
    get_ratio_contour_defaults = get_dummy_defaults

    get_confid_point_defaults = get_dummy_defaults
    get_confid_plot_defaults = get_dummy_defaults
    get_confid_contour_defaults = get_dummy_defaults
    get_model_histo_defaults = get_dummy_defaults
    get_component_plot_defaults = get_dummy_defaults
    get_component_histo_defaults = get_dummy_defaults
    get_scatter_plot_defaults = get_dummy_defaults
    get_cdf_plot_defaults = get_dummy_defaults

    def as_html_histogram(self, plot):
        return self.as_html(plot,
                    ['xlo', 'xhi', 'y', 'title', 'xlabel', 'ylabel'])


    def as_html_pdf(self, plot):
        return self.as_html(plot,
                    ['points', 'xlo', 'xhi', 'y', 'title', 'xlabel', 'ylabel'])


    def as_html_cdf(self, plot):
        return self.as_html(plot,
                    ['points', 'x', 'y',
                        'median', 'lower', 'upper',
                        'title', 'xlabel', 'ylabel'])


    def as_html_lr(self, plot):
        return self.as_html(plot,
                    ['ratios', 'lr', 'xlo', 'xhi', 'y',
                        'title', 'xlabel', 'ylabel'])


    def as_html_data(self, plot):
        return self.as_html(plot,
                    ['x', 'xerr', 'y', 'yerr',
                        'title', 'xlabel', 'ylabel'])


    def as_html_datacontour(self, plot):
        return self.as_html(plot,
                    ['x0', 'x1', 'y', 'levels',
                        'title', 'xlabel', 'ylabel'])


    def as_html_model(self, plot):
        return self.as_html(plot,
                    ['x', 'xerr', 'y', 'yerr',
                        'title', 'xlabel', 'ylabel'])


    def as_html_modelcontour(self, plot):
        return self.as_html(plot,
                    ['x0', 'x1', 'y', 'levels',
                        'title', 'xlabel', 'ylabel'])


    def get_html(self, attr):
        if attr is None:
            return ''
        return attr._repr_html_()


    def as_html_fit(self, plot):
        # Would like to do a better combination than this
        dplot = self.get_html(plot.dataplot)
        mplot = self.get_html(plot.modelplot)

        if dplot == '' and mplot == '':
            return None

        return dplot + mplot


    def as_html_fitcontour(self, plot):
        # Would like to do a better combination than this
        dplot = self.get_html(plot.datacontour)
        mplot = self.get_html(plot.modelcontour)

        if dplot == '' and mplot == '':
            return None

        return dplot + mplot


    def as_html_contour1d(self, plot):
        return self.as_html(plot,
                    ['x', 'y', 'min', 'max', 'nloop',
                        'delv', 'fac', 'log'])


    def as_html_contour2d(self, plot):
        return self.as_html(plot,
                    ['parval0', 'parval1', 'sigma',
                        'x0', 'x1', 'y', 'levels',
                        'min', 'max', 'nloop',
                        'delv', 'fac', 'log'])
