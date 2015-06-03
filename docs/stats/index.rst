
.. currentmodule:: sherpa.stats

Statistics
==========

To fit a model to a data set, Sherpa calculates the statistic value of the current
set of parameters, and then uses the optimiser to adjust the parameter values in
an attempt to lower the statistic value. Sherpa provides a number of statistics,
and these can be separated into three broad classes:

1. No error information.
2. A chi-square statistic, with a variety of ways of estimating the error
   on each point (when not given explicitly).
3. A Maximum Likelihood statistic.

When using the high-level UI, the statistic is chosen by name; for example::

    >>> from sherpa import ui
    >>> ui.set_stat('leastsq')

When using the lower-level routines, the appropriate class should be used::

    >>> from sherpa.stats import LeastSq
    >>> lsq = LeastSq()

Reference/API
-------------

.. for now just copy the docs created by sphinx-apidoc, because I do not have the
   equivalent of AstroPy's automodapi directive. I have used :noindex: here just to
   make things simple, but should perhaps change.

.. automodule:: sherpa.stats
    :members:
    :undoc-members:
    :show-inheritance:
    :noindex:
