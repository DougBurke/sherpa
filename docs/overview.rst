********
Overview
********

Sherpa is a Python package that lets the user create complex models
from simple definitions and to fit those models to data, using a
variety of statistics and optimization methods.

Provided functionality includes:

 * fit 1-D data sets (simultaneously or individually), including:
   spectra, surface brightness profiles, light curves, general ASCII arrays;

 * fit 2-D images/surfaces in the Poisson/Gaussian regime;

 * access the internal data arrays;

 * build complex model expressions;

 * import and use your own models;

 * choose appropriate statistics for modeling Poisson or Gaussian data;

 * import new statistics, with priors if required by analysis;

 * visualize a parameter space with simulations or using 1-D/2-D cuts of
   the parameter space;

 * calculate confidence levels on the best-fit model parameters;

 * choose a robust optimization method for the fit: Levenberg-Marquardt,
   Nelder-Mead Simplex or Monte Carlo/Differential Evolution;

 * perform Bayesian analysis with Poisson Likelihood and priors, using
   Metropolis or Metropolis-Hastings algorithm in the 
   MCMC (Markov-Chain Monte Carlo);

 * and use Python to create complex analysis and modeling functions,
   build the batch mode analysis or extend the provided functionality
   to meet the required needs.

.. note::

   Need to add a paragraph explaining what is meant by CIAO and
   standalone builds.

Using Sherpa
============

To support easy data ingest and analysis, Sherpa has high-level
User Interface modules (`sherpa.astro.ui` and `sherpa.ui`), which 
provide data management and utility functions. Examples of this
mode are provided in the 
`Sherpa analysis threads <http://cxc.harvard.edu/sherpa/threads/>`_
provided for users of the 
`CIAO X-ray Astronomy analyis system <http://cxc.harvard.edu/ciao/>`_.

It can also be used directly, with data management left up to the user.
This level has seen little documentation.

Optional packages
=================

Sherpa has several optional modules, most of which are determined at
compile time. This includes:

 * access to the models in the `XSpec model library <https://heasarc.gsfc.nasa.gov/xanadu/xspec/manual/Models.html>`_;

Reading and writing data
------------------------

Data reading and writing is provided by the io backend, as defined by the
``options.io_pkg`` setting in the user's ``.sherpa.rc`` file. This
can either be ``pyfits``, which uses the PyFITS_ package, 
or ``crates``, which uses the 
CIAO_ Data Model libary. Uses of the *standalone* version should
opt for ``pyfits``, although neither is required to *use* Sherpa.

.. note::

   The AstroPy_ module will soon be supported (as a replacement for PyFITS).

.. note::

   The name of the resource file depends on whether this is CIAO or
   the standalone version.

Visualization
-------------

Sherpa uses ChIPS_ and DS9_ as default packages for 1- and 2-D
visualization in CIAO, respectively, however the Sherpa plotting
functions are also compatible with the matplotlib_ package.
Users can specify in the "plot_pkg"
field of the ``.sherpa.rc`` preferences file which plotting package should
be used by Sherpa when plot commands are issued; it is "``chips``" by
default, but may be changed to "``pylab``".

.. _AstroPy: http://astropy.readthedocs.en/
.. _ChIPS: http://cxc.harvard.edu/chips/
.. _CIAO: http://cxc.harvard.edu/ciao/
.. _crates: http://cxc.harvard.edu/ciao/ahelp/crates.html
.. _CXC: http://cxc.harvard.edu/
.. _DS9: http://ds9.si.edu/
.. _FFTW: http://www.fftw.org/
.. _FITS: http://fits.gsfc.nasa.gov/
.. _IPython: http://ipython.org/
.. _matplotlib: http://matplotlib.org/
.. _PyFITS: http://www.stsci.edu/institute/software_hardware/pyfits
.. _Sphinx: http://sphinx.pocoo.org/
.. _Xspec: https://heasarc.gsfc.nasa.gov/xanadu/xspec/
