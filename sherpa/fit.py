#
#  Copyright (C) 2009, 2015, 2016, 2018-2025
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

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from functools import wraps
import logging
import os
from pathlib import Path
import signal
from typing import Any, Protocol, runtime_checkable

import numpy as np

from sherpa.data import Data, DataSimulFit
from sherpa.estmethods import EstMethod, Covariance, EstNewMin
from sherpa.models import Model, SimulFitModel
from sherpa.models.parameter import Parameter
from sherpa.optmethods import OptMethod, LevMar, NelderMead
from sherpa.stats import Stat, Chi2, Chi2Gehrels, Cash, Chi2ModVar, \
    LeastSq, Likelihood
from sherpa.utils import NoNewAttributesAfterInit, print_fields, erf, \
    bool_cast, is_iterable, list_to_open_interval, sao_fcmp, formatting
from sherpa.utils.err import DataErr, EstErr, FitErr, SherpaErr
from sherpa.utils.types import ArrayType, FitFunc, IdType, IdTypes, \
    OptReturn, StatFunc, StatResults


warning = logging.getLogger(__name__).warning
info = logging.getLogger(__name__).info

__all__ = ('FitResults', 'ErrorEstResults', 'Fit')


def evaluates_model(func):
    """Fit object decorator that runs model startup() and teardown()
    """
    @wraps(func)
    def run(fit, *args, **kwargs):

        cache = kwargs.pop('cache', True)
        fit.model.startup(cache=cache)
        result = func(fit, *args, **kwargs)
        fit.model.teardown()
        return result

    return run


class StatInfoResults(NoNewAttributesAfterInit):
    """A summary of the current statistic value for one or more data sets.

    """

    # The fields to include in the __str__ output.
    _fields = ('name', 'ids', 'bkg_ids', 'statname', 'statval',
               'numpoints', 'dof', 'qval', 'rstat')

    def __init__(self,
                 statname: str,
                 statval: float,
                 numpoints: int,
                 model,  # Why do we have this?
                 dof: int,
                 qval: float | None = None,
                 rstat: float | None = None) -> None:
        self.name: str = ''
        """The name of the data set, or sets."""

        self.ids: IdTypes | None = None
        """The data set ids (it may be a tuple or array) included
        in the results."""

        self.bkg_ids: IdTypes | None = None
        """The background data set ids (it may be a tuple or array)
        included in the results, if any."""

        self.statname: str = statname
        """The name of the statistic function."""

        self.statval: float = statval
        """The statistic value."""

        self.numpoints: int = numpoints
        """The number of bins used in the fits."""

        self.model = model

        self.dof: int = dof
        """The number of degrees of freedom in the fit (the number of
        bins minus the number of free parameters)."""

        self.qval: float | None = qval
        """The Q-value (probability) that one would observe the reduced
        statistic value, or a larger value, if the assumed model is
        true and the current model parameters are the true parameter
        values. This will be `None` if the value can not be calculated
        with the current statistic (e.g. the Cash statistic).
        """

        self.rstat: float | None = rstat
        """The reduced statistic value (the `statval` field divided by
        `dof`). This is not calculated for all statistics."""

        super().__init__()

    def __repr__(self) -> str:
        return '<Statistic information results instance>'

    def __str__(self) -> str:
        return print_fields(self._fields,
                            {k: getattr(self, k) for k in self._fields})

    def _repr_html_(self) -> str:
        """Return a HTML (string) representation of the statistics."""
        return html_statinfo(self)

    def format(self) -> str:
        """Return a string representation of the statistic.

        Returns
        -------
        txt : str
            A multi-line representation of the statistic value or values.
        """
        out = []
        if self.ids is not None and self.bkg_ids is None:
            if len(self.ids) == 1:
                out.append(f'Dataset               = {self.ids[0]}')
            else:
                # Do we remove brackets around a tuple or list?
                # idstr = str(self.ids).strip("()[]")
                idstr = str(self.ids).strip("()")
                out.append(f'Datasets              = {idstr}')

        elif self.ids is not None and self.bkg_ids is not None:
            if len(self.ids) == 1:
                out.append(f'Background {self.bkg_ids[0]} in Dataset = {self.ids[0]}')
            else:
                # It's not clear what the best way to label this, as
                # the bkg_ids may not be constant per background.
                #
                idstr = str(self.ids).strip("()")
                out.append(f'Backgrounds in Datasets = {idstr}')

        out.extend([f'Statistic             = {self.statname}',
                    f'Fit statistic value   = {self.statval:g}',
                    f'Data points           = {self.numpoints:g}',
                    f'Degrees of freedom    = {self.dof:g}'])

        if self.qval is not None:
            out.append(f'Probability [Q-value] = {self.qval:g}')

        if self.rstat is not None:
            out.append(f'Reduced statistic     = {self.rstat:g}')

        return "\n".join(out)


def _cleanup_chi2_name(stat: Stat,
                       data: Data | DataSimulFit) -> str:
    """Simplify the chi-square name if possible.

    Returns the statistic name for reporting fit results, simplifying
    the chi-square name (e.g. chi2gehrels) when possible.

    Parameters
    ----------
    stat : `sherpa.stats.Stat`
    data : `sherpa.data.Data` or `sherpa.data.DataSimulFit`

    Returns
    -------
    name : str
        The statistic name (will be 'chi2' if possible)
    """

    if isinstance(stat, LeastSq) or not isinstance(stat, Chi2):
        return stat.name

    if isinstance(data, DataSimulFit):
        is_error_set = [d.staterror is not None
                        for d in data.datasets]
        if all(is_error_set):
            return 'chi2'

    elif data.staterror is not None:
        return 'chi2'

    return stat.name


class FitResults(NoNewAttributesAfterInit):
    """The results of a fit.

    This object contains the parameter values, information on the
    statistic and optimisation-method used, and other relevant
    information.

    .. versionchanged:: 4.10.1
       The ``covarerr`` attribute has been renamed to ``covar``
       and now contains the covariance matrix estimated at the
       best-fit location, if provided by the optimiser.

    .. versionchanged:: 4.17.1
       The `record_steps` attribute has been added to the class.
       If the fit recorded the parameter values of each step in the optimization,
       this attribute will contain an array with the data.
    """

    # The fields to include in the __str__ output.
    _fields = ('datasets', 'itermethodname', 'methodname', 'statname',
               'succeeded', 'parnames', 'parvals', 'statval', 'istatval',
               'dstatval', 'numpoints', 'dof', 'qval', 'rstat', 'message',
               'nfev')

    def __init__(self,
                 fit: Fit,
                 results: OptReturn,
                 init_stat: float,
                 param_warnings: str
                 ) -> None:
        _vals = fit.data.eval_model_to_fit(fit.model)
        _dof = len(_vals) - len(tuple(results[1]))
        _covar = results[4].get('covar')
        _rstat, _qval = fit.stat.goodness_of_fit(results[2], _dof)

        self.succeeded: bool = results[0]
        """Was the fit successful (did it converge)?"""

        self.parnames: tuple[str, ...] = tuple(p.fullname for p in fit.model.get_thawed_pars())
        """The parameter names that were varied in the fit,

        This is the thawed parameters in the model expression.
        """

        self.parvals: tuple[float, ...] = tuple(float(r) for r in results[1])
        """The parameter values, in the same order as `parnames`."""

        self.istatval: float = init_stat
        """The statistic value at the start of the fit."""

        self.statval: float = float(results[2])
        """The statistic value after the fit."""

        self.dstatval: float = np.abs(self.statval - init_stat)
        """The change in the statistic value (``istatval - statval``)."""

        self.numpoints: int = len(_vals)
        """The number of bins used in the fits."""

        self.dof: int = _dof
        """The number of degrees of freedom in the fit (the number of
        bins minus the number of free parameters)."""

        self.qval: float | None = _qval
        """The Q-value (probability) that one would observe the
        reduced statistic value, or a larger value, if the assumed
        model is true and the current model parameters are the true
        parameter values.

        This will be `None` if the value can not be calculated with
        the current statistic (e.g. the Cash statistic).

        """

        self.rstat: float | None = _rstat
        """The reduced statistic value (the `statval` field divided by
        `dof`).

        This is not calculated for all statistics."""

        self.message: str = results[3]
        """A message about the results of the fit (e.g. if the fit was
        unable to converge).

        The format and contents depend on the optimisation method."""

        # What is the best type here?
        self.covar = _covar
        """The covariance matrix from the best-fit location, if provided
        by the optimiser."""

        self.nfev: int = results[4].get('nfev')
        """The number of model evaluations made during the fit."""

        # What is the best type here?
        self.extra_output = results[4]
        """The ``extra_output`` field from the fit."""

        self.record_steps: None | dict = results[4].get('record_steps')
        """A record of all steps taken during the fit, if requested
        with `record_steps=True`."""

        self.modelvals: np.ndarray = _vals
        """The values of the best-fit model evaluated for the data."""

        self.methodname: str = type(fit.method).__name__.lower()
        """The name of the optimisation method used (in lower case)."""

        self.itermethodname: str | None = fit._iterfit.itermethod_opts['name']
        """What iterated-fit scheme was used, if any."""

        statname = _cleanup_chi2_name(fit.stat, fit.data)
        self.statname: str = statname
        """The name of the statistic function."""

        # To be filled by calling function
        self.datasets: list[IdType] | None = None
        """A sequence of the data set ids included in the results."""

        self.param_warnings = param_warnings

        super().__init__()

    def __setstate__(self, state):
        self.__dict__.update(state)

        if 'itermethodname' not in state:
            self.__dict__['itermethodname'] = 'none'

    def __bool__(self) -> bool:
        return self.succeeded

    def __repr__(self) -> str:
        return '<Fit results instance>'

    def __str__(self) -> str:
        return print_fields(self._fields, vars(self))

    def _repr_html_(self) -> str:
        """Return a HTML (string) representation of the fit results."""
        return html_fitresults(self)

    def format(self) -> str:
        """Return a string representation of the fit results.

        Returns
        -------
        txt : str
            A multi-line representation of the fit results.
        """
        out = []
        if self.datasets is not None:
            if len(self.datasets) == 1:
                out.append(f'Dataset               = {self.datasets[0]}')
            else:
                # Do we remove brackets around a tuple or list?
                # idstr = str(self.datasets).strip("()[]")
                idstr = str(self.datasets).strip("()")
                out.append(f'Datasets              = {idstr}')

        if self.itermethodname is not None and self.itermethodname != 'none':
            out.append(f'Iterative Fit Method  = {self.itermethodname.capitalize()}')

        out.extend([f'Method                = {self.methodname}',
                    f'Statistic             = {self.statname}',
                    f'Initial fit statistic = {self.istatval:g}'])

        outstr = f'Final fit statistic   = {self.statval:g}'
        if self.nfev is not None:
            outstr += f' at function evaluation {self.nfev}'

        out.extend([outstr,
                    f'Data points           = {self.numpoints:g}',
                    f'Degrees of freedom    = {self.dof:g}'])

        if self.qval is not None:
            out.append(f'Probability [Q-value] = {self.qval:g}')

        if self.rstat is not None:
            out.append(f'Reduced statistic     = {self.rstat:g}')

        out.append(f'Change in statistic   = {self.dstatval:g}')

        if self.covar is None:
            out.extend(f'   {name:<12s}   {val:<12g}'
                       for name, val in zip(self.parnames, self.parvals))
        else:
            covar_err = np.sqrt(self.covar.diagonal())
            out.extend(f'   {name:<12s}   {val:<12g} +/- {covarerr:<12g}'
                       for name, val, covarerr in zip(self.parnames,
                                                      self.parvals,
                                                      covar_err))

        if self.param_warnings != "":
            out.append(self.param_warnings)

        return "\n".join(out)


class ErrorEstResults(NoNewAttributesAfterInit):
    """The results of an error estimation run.

    This object contains the parameter ranges, information on the
    statistic and optimisation-method used, and other relevant
    information.

    """

    # The fields to include in the __str__ output.
    _fields = ('datasets', 'methodname', 'iterfitname', 'fitname', 'statname',
               'sigma', 'percent', 'parnames', 'parvals', 'parmins',
               'parmaxes', 'nfits')

    def __init__(self,
                 fit: Fit,
                 results,
                 parlist: Sequence[Parameter] | None = None
                 ) -> None:

        # Avoid an import loop.
        #
        from sherpa.estmethods import est_hardmin, est_hardmax, \
            est_hardminmax

        if parlist is None:
            pars = fit.model.get_thawed_pars()
        else:
            pars = parlist

        # To be set by calling function
        self.datasets: list[IdType] | None = None
        """A sequence of the data set ids included in the results."""

        self.methodname: str = type(fit.estmethod).__name__.lower()
        """The name of the optimisation method used (in lower case)."""

        self.iterfitname: str | None = fit._iterfit.itermethod_opts['name']
        """What iterated-fit scheme was used, if any."""

        self.fitname: str = type(fit.method).__name__.lower()
        """The name of the method used to fit the data, in lower case."""

        self.statname: str = type(fit.stat).__name__.lower()
        """The name of the statistic used to fit the data, in lower case."""

        self.sigma: float = fit.estmethod.sigma
        """The error values represent this number of sigma (assuming a
        Gaussian distribution)."""

        self.percent: float = erf(self.sigma / np.sqrt(2.0)) * 100.0
        """The percentage value for the errors (calculated from the
        ``sigma`` value assuming Gaussian errors)."""

        self.parnames: tuple[str, ...] = tuple(p.fullname for p in pars if not p.frozen)
        """The parameter names that were varied in the fit
        (the thawed parameters in the model expression)."""

        self.parvals: tuple[float, ...] = tuple(float(p.val) for p in pars if not p.frozen)
        """The parameter values, in the same order as `parnames`."""

        pmins = []
        pmaxes = []
        for i in range(len(pars)):
            if (results[2][i] == est_hardmin or
                results[2][i] == est_hardminmax or
                results[0][i] is None  # It looks like confidence does not set the flag
                ):
                pmins.append(None)
                warning("hard minimum hit for parameter %s", self.parnames[i])
            else:
                pmins.append(float(results[0][i]))

            if (results[2][i] == est_hardmax or
                results[2][i] == est_hardminmax or
                results[1][i] is None  # It looks like confidence does not set the flag
                ):
                pmaxes.append(None)
                warning("hard maximum hit for parameter %s", self.parnames[i])
            else:
                pmaxes.append(float(results[1][i]))

        self.parmins: tuple[float, ...] = tuple(pmins)
        """The parameter minimum values, in the same order as `parnames`."""

        self.parmaxes: tuple[float, ...] = tuple(pmaxes)
        """The parameter maximum values, in the same order as `parnames`."""

        self.nfits: int = results[3]
        """The number of fits performed during the error analysis."""

        # What is the best type here?
        self.extra_output = results[4]
        """The ``extra_output`` field from the fit."""

        super().__init__()

    def __setstate__(self, state):
        self.__dict__.update(state)

        if 'iterfitname' not in state:
            self.__dict__['iterfitname'] = 'none'

    def __repr__(self) -> str:
        return f'<{self.methodname} results instance>'

    def __str__(self) -> str:
        return print_fields(self._fields, vars(self))

    def _repr_html_(self) -> str:
        """Return a HTML (string) representation of the error estimates."""
        return html_errresults(self)

    def format(self) -> str:
        """Return a string representation of the error estimates.

        Returns
        -------
        txt : str
            A multi-line representation of the error estimates.
        """

        out = []
        if self.datasets is not None:
            if len(self.datasets) == 1:
                out.append(f'Dataset               = {self.datasets[0]}')
            else:
                out.append(f'Datasets              = {self.datasets}')

        out.append(f'Confidence Method     = {self.methodname}')

        if self.iterfitname is not None and self.iterfitname != 'none':
            out.append(f'Iterative Fit Method  = {self.iterfitname.capitalize()}')

        out.extend([f'Fitting Method        = {self.fitname}',
                    f'Statistic             = {self.statname}',
                    f"{self.methodname} {self.sigma:g}-sigma ({self.percent:2g}%) bounds:"])

        def myformat(hfmt, lowstr, lownum, highstr, highnum):
            out = hfmt % ('Param', 'Best-Fit', 'Lower Bound', 'Upper Bound')
            out += hfmt % ('-' * 5, '-' * 8, '-' * 11, '-' * 11)

            for name, val, lower, upper in zip(self.parnames, self.parvals,
                                               self.parmins, self.parmaxes):

                out += f'\n   {name:<12s} {val:12g} '
                if is_iterable(lower):
                    out += ' '
                    out += list_to_open_interval(lower)
                elif lower is None:
                    out += lowstr % '-----'
                else:
                    out += lownum % lower
                if is_iterable(upper):
                    out += '  '
                    out += list_to_open_interval(upper)
                elif upper is None:
                    out += highstr % '-----'
                else:
                    out += highnum % upper

            return out

        in_low = True in map(is_iterable, self.parmins)
        in_high = True in map(is_iterable, self.parmaxes)
        mymethod = self.methodname == 'confidence'

        lowstr = '%12s '
        lownum = '%12g '
        highstr = '%12s'
        highnum = '%12g'

        if in_low and in_high and mymethod:
            hfmt = '\n   %-12s %12s %29s %29s'
            lowstr = '%29s '
            lownum = '%29g '
            highstr = '%30s'
            highnum = '%30g'
        elif in_low and not in_high and mymethod:
            hfmt = '\n   %-12s %12s %29s %12s'
            lowstr = '%29s '
            lownum = '%29g '
            highstr = '%13s'
            highnum = '%13g'
        elif not in_low and in_high and mymethod:
            hfmt = '\n   %-12s %12s %12s %29s'
            highstr = '%29s'
            highnum = '%29g'
        else:
            hfmt = '\n   %-12s %12s %12s %12s'

        return "\n".join(out) + myformat(hfmt, lowstr, lownum, highstr, highnum)


# Rather than use typing.TextIO just define what operations we
# need. Follows https://github.com/python/typing/discussions/829
#
@runtime_checkable
class WriteableTextFile(Protocol):
    """An object that supports write() and close()."""

    def write(self, s: str, /) -> int: ...

    def close(self) -> None: ...


class IterCallback:
    """Update the model with the suggested parameters.

    This defines the interface returned by the _get_callback method
    for the IterFit class. It is not intended for external use at this
    time.

    """

    __slots__ = ("data", "model", "stat", "fh", "nfev", "record_steps")

    def __init__(self,
                 data: DataSimulFit,
                 model: SimulFitModel,
                 stat: Stat,
                 fh: WriteableTextFile | None = None,
                 record_steps: bool = False
                 ) -> None:
        self.data = data
        self.model = model
        self.stat = stat
        self.fh = fh
        self.nfev = 0
        self.record_steps = [] if record_steps else None

    def __call__(self,
                 pars: np.ndarray
                 ) -> tuple[float, np.ndarray]:
        "Evaluate the statistic, increase nfev, and maybe update the fh."

        # Update the parameter values
        self.model.thawedpars = pars

        # The return value
        output = self.stat.calc_stat(self.data, self.model)

        # Write out the data, if requested. This is done before nfev
        # is updated.
        #
        if self.fh is not None:
            vals = [f'{self.nfev:5e}', f'{output[0]:5e}']
            vals.extend([f'{val:5e}' for val in self.model.thawedpars])
            self.fh.write(' '.join(vals) + '\n')

        if self.record_steps is not None:
            # Store the current parameter values
            self.record_steps.append((self.nfev, output[0], *self.model.thawedpars))

        # Update the counter and return the results
        self.nfev += 1
        return output


# Since this is an internal class, it's not derived from
# NoNewAttributesAfterInit.
#
# It might be nice to make many of the fields read-only or to
# be tied to the enclosing Fit object, but that would add extra
# complexity which does not seem worth it at this time - see
# issue #2063
#
class IterFit:
    """Support iterative fitting schemes.

    This class is highly coupled to `Fit`.

    .. versionchanged:: 4.17.0
       Several internal fields have been removed as they are now
       handled by the IterCallback class and the changes to the
       _get_callback routine.

    """

    def __init__(self,
                 # DataSimulFit does not derive from Data, but
                 # SimulFitModel does derive from Model.
                 data: Data | DataSimulFit,
                 model: Model,
                 stat: Stat,
                 method: OptMethod,
                 itermethod_opts: Mapping[str, Any] | None = None
                 ) -> None:
        if itermethod_opts is None:
            iopts = {'name': 'none'}
        else:
            iopts = itermethod_opts

        # Even if there is only a single data set, I will
        # want to treat the data and models I am given as
        # collections of data and models -- so, put data and
        # models into the objects needed for simultaneous fitting,
        # if they are not already in such objects.
        #
        if isinstance(data, DataSimulFit):
            self.data = data
        else:
            self.data = DataSimulFit('simulfit data', (data,))

        if isinstance(model, SimulFitModel):
            self.model = model
        else:
            self.model = SimulFitModel('simulfit model', (model,))

        self.stat = stat
        self.method = method
        # Data set attributes needed to store fitting values between
        # calls to fit
        self._dep = None
        # self.extra_args = None
        self._staterror = None
        self._syserror = None

        # Options to send to iterative fitting method
        self.itermethod_opts = iopts

        self.funcs: dict[str, FitFunc]
        self.funcs = {'sigmarej': self.sigmarej}

        self.current_func: FitFunc | None
        self.current_func = None
        try:
            iname = self.itermethod_opts['name']
        except KeyError:
            raise ValueError("Missing name field in itermethod_opts argument") from None

        if iname != 'none':
            try:
                self.current_func = self.funcs[iname]
            except KeyError:
                raise ValueError(f"{iname} is not an iterative fitting method") from None

    # SIGINT (i.e., typing ctrl-C) can dump the user to the Unix prompt,
    # when signal is sent from G95 compiled code.  What we want is to
    # get to the Sherpa prompt instead.  Typically the user only thinks
    # to interrupt during long fits or projection, so look for SIGINT
    # here, and if it happens, raise the KeyboardInterrupt exception
    # instead of aborting.
    def _sig_handler(self, signum, frame):
        raise KeyboardInterrupt()

    def _get_callback(self,
                      fh: WriteableTextFile | None = None,
                      record_steps: bool = False,
                      ) -> IterCallback:
        """Create the function that returns the statistic.

        If fh is set then each set of parameters, along with the
        statistic, are written out to the handle.

        .. versionchanged:: 4.17.0
           The routine now accepts an optional fh parameter rather
           than outfile and clobber. The calling routine is
           responsible for setting up the argument.

        """
        if len(self.model.thawedpars) == 0:
            raise FitErr('nothawedpar')

        # support Sherpa use with SAMP
        try:
            signal.signal(signal.SIGINT, self._sig_handler)
        except ValueError as e:
            warning(e)

        # Store the original set of data that is to be fit.
        #
        self._dep, self._staterror, self._syserror = self.data.to_fit(
            self.stat.calc_staterror)

        return IterCallback(data=self.data, model=self.model,
                            stat=self.stat, fh=fh,
                            record_steps=record_steps)

    # TODO: look at the cache argument
    def sigmarej(self,
                 statfunc: StatFunc,
                 pars: ArrayType,
                 parmins: ArrayType,
                 parmaxes: ArrayType,
                 statargs: Any = None,
                 statkwargs: Any = None,
                 cache: bool = True
                 ) -> OptReturn:
        """Exclude points that are significately far away from the best fit.

        The `sigmarej` scheme is based on the IRAF ``sfit`` function,
        where after a fit data points are excluded if the value
        of ``(data-model) / error`` exceeds a threshold, and the data
        re-fit. This removal of data points continues until the fit
        has converged or a maximum number of iterations has been reached.
        The error removal can be asymmetric, since there are separate
        options for the lower and upper limits.

        .. versionchanged:: 4.18.0
           The statargs and statkwargs arguments are now ignored.

        Raises
        ------
        `sherpa.utils.err.FitErr`
            This exception is raised if the statistic is not
            supported. This method can only be used with
            Chi-Square statistics with errors.

        Notes
        -----
        The following keys are looked for in the `itermethod_opts`
        dictionary:

        ========  ==========  ===========
        Key       Type        Description
        ========  ==========  ===========
        maxiters  int > 0     The maximum number of iterations.
        lrej      number > 0  The number of sigma below the model to reject.
        hrej      number > 0  The number of sigma above the model to reject.
        grow      int >= 0    If greater than zero, also remove this many data
                              points to either side of the identified element.
        ========  ==========  ===========

        """

        if statargs is not None or statkwargs is not None:
            warning("statargs/kwargs set but values unused")

        # Sigma-rejection can only be used with chi-squared;
        # raise exception if it is attempted with least-squares,
        # or maximum likelihood.
        #
        if not (isinstance(self.stat, Chi2) and
                type(self.stat) is not LeastSq):
            raise FitErr('needchi2', 'Sigma-rejection')

        # Get maximum number of allowed iterations, high and low
        # sigma thresholds for rejection of data points, and
        # "grow" factor (i.e., how many surrounding data points
        # to include with rejected data point).

        maxiters = self.itermethod_opts['maxiters']
        if not isinstance(maxiters, int):
            raise SherpaErr(
                "'maxiters' value for sigma rejection method must be an integer")
        if maxiters < 1:
            raise SherpaErr("'maxiters' must be one or greater")

        hrej = self.itermethod_opts['hrej']
        if not isinstance(hrej, (int, float)):
            raise SherpaErr(
                "'hrej' value for sigma rejection method must be a number")
        if hrej <= 0:
            raise SherpaErr("'hrej' must be greater than zero")

        lrej = self.itermethod_opts['lrej']
        # FIXME: [OL] There are more reliable ways of checking if an object
        # is (not) a number.
        if not isinstance(lrej, (int, float)):
            raise SherpaErr(
                "'lrej' value for sigma rejection method must be a number")
        if lrej <= 0:
            raise SherpaErr("'lrej' must be greater than zero")

        grow = self.itermethod_opts['grow']
        if not isinstance(grow, int):
            raise SherpaErr(
                "'grow' value for sigma rejection method must be an integer")
        if grow < 0:
            raise SherpaErr("'grow' factor must be zero or greater")

        nfev = 0
        iters = 0

        # Store original masks (filters) for each data set.
        mask_original = []

        for d in self.data.datasets:
            # If there's no filter, create a filter that is
            # all True
            if not np.iterable(d.mask):
                mask_original.append(d.mask)
                d.mask = np.ones_like(np.array(d.get_dep(False), dtype=bool))
            else:
                mask_original.append(np.array(d.mask))

        # QUS: why is teardown being called now when the model can be
        #      evaluated multiple times in the following loop?
        #      Note that after the loop  self.model.startup
        #      is called, so either I [DJB] or the code has them the
        #      wrong way around
        self.model.teardown()

        final_fit_results = None
        rejected = True
        try:
            while rejected and iters < maxiters:
                # Update stored y, staterror and syserror values
                # from data, so callback function will work properly
                self._dep, self._staterror, self._syserror = self.data.to_fit(
                    self.stat.calc_staterror)
                self.model.startup(cache)
                final_fit_results = self.method.fit(statfunc,
                                                    pars=self.model.thawedpars,
                                                    parmins=parmins,
                                                    parmaxes=parmaxes)
                model_iterator = iter(self.model())
                rejected = False

                for d in self.data.datasets:
                    # For each data set, compute
                    # (data - model) / staterror
                    # over filtered data space
                    residuals = (d.get_dep(True) - d.eval_model_to_fit(
                        next(model_iterator))) / d.get_staterror(True, self.stat.calc_staterror)

                    # For each modeled value that exceeds
                    # sigma thresholds, set the corresponding
                    # filter value from True to False
                    ressize = len(residuals)
                    filsize = len(d.mask)
                    newmask = d.mask

                    j = 0
                    kmin = 0
                    for i in range(0, ressize):
                        while not(newmask[j]) and j < filsize:
                            j = j + 1
                        if j >= filsize:
                            break
                        if residuals[i] <= -lrej or residuals[i] >= hrej:
                            rejected = True
                            kmin = max(j - grow, 0)
                            kmax = j + grow
                            if kmax >= filsize:
                                kmax = filsize - 1
                            for k in range(kmin, kmax + 1):
                                newmask[k] = False
                        j = j + 1

                        # If we've masked out *all* data,
                        # immediately raise fit error, clean up
                        # on way out.
                        if not np.any(newmask):
                            raise FitErr('nobins')
                        d.mask = newmask

                # For data sets with backgrounds, correct that
                # backgrounds have masks that match their sources
                for d in self.data.datasets:
                    if (hasattr(d, "background_ids") and
                            hasattr(d, "get_background")):
                        for bid in d.background_ids:
                            b = d.get_background(bid)
                            if np.iterable(b.mask) and np.iterable(d.mask):
                                if len(b.mask) == len(d.mask):
                                    b.mask = d.mask

                # teardown model, get ready for next iteration
                self.model.teardown()
                iters = iters + 1
                nfev += final_fit_results[4].get('nfev')
                final_fit_results[4]['nfev'] = nfev
        except:
            # Clean up if exception occurred
            mask_original.reverse()
            for d in self.data.datasets:
                d.mask = mask_original.pop()

            # Update stored y, staterror and syserror values
            # from data, so callback function will work properly
            self._dep, self._staterror, self._syserror = self.data.to_fit(
                self.stat.calc_staterror)
            self.model.startup(cache)
            raise

        self._dep, self._staterror, self._syserror = self.data.to_fit(
            self.stat.calc_staterror)

        # QUS: shouldn't this be teardown, not startup?
        self.model.startup(cache)

        # N.B. -- If sigma-rejection in Sherpa 3.4 succeeded,
        # it did *not* restore the filter to its state before
        # sigma-rejection was called.  If points are filtered
        # out, they stay out.  So we emulate the same behavior
        # if our version of sigma-rejection succeeds.

        # Mind you, if sigma-rejection *fails*, then we *do*
        # restore the filter, and re-raise the exception in
        # the above exception block.

        # Return results from sigma rejection
        assert final_fit_results is not None  # safety check
        return final_fit_results

    def fit(self,
            statfunc: StatFunc,
            pars: ArrayType,
            parmins: ArrayType,
            parmaxes: ArrayType,
            statargs: Any = None,
            statkwargs: Any = None
            ) -> OptReturn:
        """

        .. versionchanged:: 4.18.0
           The statargs and statkwargs arguments are now ignored.

        """

        if statargs is not None or statkwargs is not None:
            warning("statargs/kwargs set but values unused")

        if self.current_func is None:
            return self.method.fit(statfunc, pars=pars,
                                   parmins=parmins, parmaxes=parmaxes)

        return self.current_func(statfunc, pars=pars, parmins=parmins,
                                 parmaxes=parmaxes)


# What is the best way to annotate the return value here?
#
def _add_fit_stats(outfile: str | Path | WriteableTextFile | None,
                   clobber: bool,
                   names: Sequence[str]):
    """Handle creating the output file handle for the fit callback.

    If there is a file handle or file specified then write the
    header. The return value should be used as a context manager to
    ensure that the handle is closed (when outfile is a string or a
    path).

    """

    if outfile is None:
        return nullcontext(None)

    if isinstance(outfile, WriteableTextFile):
        fh = outfile
    else:
        # os.path.isfile and open accepts strings and Path objects
        if not clobber and os.path.isfile(outfile):
            raise FitErr('noclobererr', str(outfile))

        fh = open(outfile, mode='w', encoding="ascii")

    # Write out the header line
    hdr = ['#', 'nfev', 'statistic']
    hdr.extend(names)
    fh.write(' '.join(hdr) + '\n')

    if isinstance(outfile, WriteableTextFile):
        return nullcontext(fh)

    return fh


def _check_length(dep) -> int:
    """Check there is data to fit (the array is not empty).

    Returns the length of the data.
    """

    # This is partly written this way to appease mypy.
    try:
        ndep = len(dep)
        if ndep > 0:
            return ndep

    except TypeError:
        # Assume does not have a length.
        pass

    raise FitErr('nobins')


class Fit(NoNewAttributesAfterInit):
    """Fit a model to a data set.

    .. versionchanged:: 4.17.0
       Changing the stat field now changes the internal IterFit
       object as well.

    Parameters
    ----------
    data : `sherpa.data.Data` or `sherpa.data.DataSimulFit`
       The data to be fit.
    model : `sherpa.models.model.Model` or `sherpa.models.model.SimulFitModel`
       The model to fit to the data. It should match the ``data`` parameter
       (i.e. be a `SimulFitModel` object when data is a `DataSimulFit`).
    stat : `sherpa.stats.Stat` or `None`, optional
       The statistic object to use. If not given then
       `Chi2Gehrels` is used.
    method : `sherpa.optmethods.OptMethod` instance or None, optional
       The optimiser to use. If not given then `sherpa.optmethods.LevMar`
       is used.
    estmethod : `sherpa.estmethods.EstMethod` or None, optional
       The class used to calculate errors. If not given then
       `sherpa.estmethods.Covariance` is used.
    itermethod_opts : dict or None, optional
       If set, defines the iterated-fit method and options to use.
       It is passed through to `IterFit`.

    """

    def __init__(self,
                 # DataSimulFit does not derive from Data, but
                 # SimulFitModel does derive from Model.
                 data: Data | DataSimulFit,
                 model: Model,
                 stat: Stat | None = None,
                 method: OptMethod | None = None,
                 estmethod: EstMethod | None = None,
                 itermethod_opts: Mapping[str, Any] | None = None
                 ) -> None:

        # Ensure the data and model match dimensionality. It is
        # expected that both data and model have a ndim attribute
        # but allow them to be missing (e.g. user-defined or
        # loaded from a pickled file before ndim was added).
        #
        ddim = getattr(data, 'ndim', None)
        mdim = getattr(model, 'ndim', None)
        if None not in [mdim, ddim] and mdim != ddim:
            raise DataErr(f"Data and model dimensionality do not match: {ddim}D and {mdim}D")

        if itermethod_opts is None:
            iopts = {'name': 'none'}
        else:
            iopts = itermethod_opts

        self.data = data
        self.model = model

        # It is not clear why this can not just set self.stat but
        # there is a comment below that suggests it should not be done
        # here.
        #
        statobj = Chi2Gehrels() if stat is None else stat

        self.method = LevMar() if method is None else method
        self.estmethod = Covariance() if estmethod is None else estmethod
        self.current_frozen = -1

        # The number of times that reminimization has occurred
        # during an attempt to compute confidence limits.  If
        # that number equals self.estmethod.maxfits, cease all
        # further attempt to reminimize.
        self.refits = 0

        # Set up an IterFit object, so that the user can select
        # an iterative fitting option.
        self._iterfit = IterFit(self.data, self.model, statobj,
                                self.method, iopts)

        # We need to set the statistic *after* creating the _iterfit
        # attribute
        #
        self.stat = statobj

        super().__init__()

    @property
    def stat(self) -> Stat:
        """Return the statistic value"""
        return self._stat

    @stat.setter
    def stat(self, stat: Stat) -> None:
        """Ensure that we use a consistent stat object."""
        self._stat = stat
        self._iterfit.stat = stat

    def __setstate__(self, state):
        self.__dict__.update(state)

        if '_iterfit' not in state:
            self.__dict__['_iterfit'] = IterFit(self.data, self.model,
                                                self.stat, self.method,
                                                {'name': 'none'})

    def __str__(self) -> str:
        out = [f'data      = {self.data.name}',
               f'model     = {self.model.name}',
               f'stat      = {type(self.stat).__name__}',
               f'method    = {type(self.method).__name__}',
               f'estmethod = {type(self.estmethod).__name__}']
        return "\n".join(out)

    def guess(self, **kwargs) -> None:
        """Guess parameter values and limits.

        The model's `sherpa.models.model.Model.guess` method
        is called with the data values (the dependent axis of the
        data set) and the ``kwargs`` arguments.
        """
        self.model.guess(*self.data.to_guess(), **kwargs)

    # QUS: should this have an @evaluates_model decorator?
    def _calc_stat(self) -> StatResults:
        """Calculate the current statistic value.

        Returns
        -------
        statval, fvec : number, array of numbers
            The overall statistic value and the "per-bin" value.
        """

        # TODO: is there anything missing here that
        #       self._iterfit.get_extra_args calculates?
        return self.stat.calc_stat(self.data, self.model)

    def calc_stat(self) -> float:
        """Calculate the statistic value.

        Evaluate the statistic for the current model and data
        settings (e.g. parameter values and data filters).

        Returns
        -------
        stat : number
           The current statistic value.

        See Also
        --------
        calc_chisqr, calc_stat_info

        """

        return self._calc_stat()[0]

    def calc_chisqr(self) -> np.ndarray | None:
        """Calculate the per-bin chi-squared statistic.

        Evaluate the per-bin statistic for the current model and data
        settings (e.g. parameter values and data filters).

        Returns
        -------
        chisq : array or None
           The chi-square value for each bin of the data, using the
           current statistic.
           A value of `None` is returned if the statistic is not a chi-square
           distribution.

        See Also
        --------
        calc_stat, calc_stat_info
        """

        # Since there is some setup work needed before calling
        # this routine, and to avoid catching any AttributeErrors
        # thrown by the routine, use this un-pythonic check.
        #
        if not hasattr(self.stat, 'calc_chisqr'):
            return None

        return self.stat.calc_chisqr(self.data, self.model)

    def calc_stat_info(self) -> StatInfoResults:
        """Calculate the statistic value and related information.

        Evaluate the statistic for the current model and data
        settings (e.g. parameter values and data filters).

        Returns
        -------
        statinfo : `StatInfoResults` instance
           The current statistic value.

        See Also
        --------
        calc_chisqr, calc_stat

        """

        # TODO: This logic would be better in the stat class than here
        #
        statval, fvec = self._calc_stat()
        model = self.data.eval_model_to_fit(self.model)

        numpoints = len(model)
        dof = numpoints - len(self.model.thawedpars)

        rstat, qval = self.stat.goodness_of_fit(statval, dof)

        name = _cleanup_chi2_name(self.stat, self.data)

        return StatInfoResults(name, statval, numpoints, model,
                               dof, qval, rstat)

    # TODO: the numcores argument is currently unused.
    #
    @evaluates_model
    def fit(self,
            outfile: str | Path | WriteableTextFile | None = None,
            clobber: bool = False,
            numcores: int | None = 1,
            record_steps: bool = False,
            ) -> FitResults:
        """Fit the model to the data.

        .. versionchanged:: 4.17.0
           The outfile parameter can now be sent a Path object or a
           file handle instead of a string.

        .. versionchanged:: 4.17.1
           The parameter ``record_steps`` was added to keep parameter
           values of each iteration in the `FitResults` object that is
           returned.

        Parameters
        ----------
        outfile : str, Path, IO object, or None, optional
            If not `None` then information on the fit is written to
            this file (as defined by a filename, path, or file
            handle).
        clobber : bool, optional
            Determines if the output file can be overwritten. This is
            only used when `outfile` is a string or `Path` object.
        numcores : int or None, optional
            The number of cores to use in fitting simultaneous data.
            This argument is currently unused.
        record_steps : bool, optional
            If `True`, then the parameter values and statistic value
            are recorded at each iteration in a dictionary in the
            `FitResults` object that this method returns.

        Returns
        -------
        fitres : `FitResults`

        Raises
        ------
        `sherpa.utils.err.FitErr`
           This is raised if ``clobber`` is ``False`` and ``outfile`` already
           exists or if all the bins have been masked out of the fit.

        See Also
        --------
        est_errors, simulfit

        Notes
        -----
        The file created when ``outfile`` is set is a simple ASCII
        file with a header line containing the text
        "# nfev statistic" and then a list of the thawed parameters,
        and then one line for each iteration, with the values separated
        by spaces. If ``outfile`` is sent a file handle it is not
        closed by this routine.

        Examples
        --------

        Fit a very-simple model (a constant value) to a small 1D
        dataset:

        >>> from sherpa.data import Data1D
        >>> from sherpa.models.basic import Const1D
        >>> from sherpa.stats import LeastSq
        >>> from sherpa.fit import Fit
        >>> d = Data1D("x", [-3, 5, 17, 22], [12, 3, 8, 5])
        >>> m = Const1D()
        >>> s = LeastSq()
        >>> f = Fit(d, m, stat=s)
        >>> out = f.fit()
        >>> if not out.succeeded: print("Fit failed")
        >>> print(out.format())
        Method                = levmar
        Statistic             = leastsq
        Initial fit statistic = 190
        Final fit statistic   = 46 at function evaluation 4
        Data points           = 4
        Degrees of freedom    = 3
        Change in statistic   = 144
           const1d.c0     7            +/- 0.5

        >>> print(m)
        const1d
           Param        Type          Value          Min          Max      Units
           -----        ----          -----          ---          ---      -----
           const1d.c0   thawed            7 -3.40282e+38  3.40282e+38

        Repeat the fit, after resetting the model, so we can see how
        the optimiser searched the parameter space:

        >>> m.reset()
        >>> out = f.fit(record_steps=True)
        >>> for row in out.record_steps:
        ...     print(f"{row['nfev']} {row['statistic']:8.6e} {row['const1d.c0']:6.4f}")
        0 1.900000e+02 1.0000
        1 1.900000e+02 1.0000
        2 1.899834e+02 1.0003
        3 4.600000e+01 7.0000
        4 4.600002e+01 7.0024
        5 4.600000e+01 7.0000

        This format is also easy to plot, e.g.
        ``plt.plot(out.record_steps['nfev'], out.record_steps['statistic'])``.

        Output could also be file-based or captured using `io.StringIO`:

        >>> from io import StringIO
        >>> m.reset()
        >>> optdata = StringIO()
        >>> out2 = f.fit(outfile=optdata)
        >>> print(optdata.getvalue())
        # nfev statistic const1d.c0
        0.000000e+00 1.900000e+02 1.000000e+00
        1.000000e+00 1.900000e+02 1.000000e+00
        2.000000e+00 1.899834e+02 1.000345e+00
        3.000000e+00 4.600000e+01 7.000000e+00
        4.000000e+00 4.600002e+01 7.002417e+00
        5.000000e+00 4.600000e+01 7.000000e+00
        """

        dep, staterror, _ = self.data.to_fit(self.stat.calc_staterror)

        # TODO: This test may already be handled by data.to_fit(),
        #       which raises DataErr('notmask'), although I have not
        #       investigated if it is possible to pass that check
        #       but fail the following.
        #
        _check_length(dep)

        if ((np.iterable(staterror) and 0.0 in staterror) and
                isinstance(self.stat, Chi2) and
                type(self.stat) is not Chi2 and
                type(self.stat) is not Chi2ModVar):
            raise FitErr('binhas0')

        init_stat = self.calc_stat()

        names = [par.fullname
                 for par in self.model.get_thawed_pars()]
        cm = _add_fit_stats(outfile, clobber, names)
        with cm as fh:
            cb = self._iterfit._get_callback(fh=fh,
                                             record_steps=record_steps)
            output_orig = self._iterfit.fit(cb,
                                            self.model.thawedpars,
                                            self.model.thawedparmins,
                                            self.model.thawedparmaxes)

            (status, newpars, fval, msg, imap) = output_orig

            # Do a final update. It's not clear if this is because the
            # optimization interface does not guarantee that the
            # "best-fit" parameters have been passed to cb, or whether
            # something else is going on (prior to fixing #2063 we did
            # have the case that self.stat and self._iterfit.stat were
            # not guaranteed to be the same).
            #
            # Could we skip this if newpars is the same as thawedpars?
            #
            fval_new, _ = cb(newpars)

            # Check if any parameter values are at boundaries, and warn
            # user. This does not include any linked parameters.
            #
            tol = np.finfo(np.float32).eps
            param_warnings = ""
            for par in self.model.pars:
                if not par.frozen:
                    if sao_fcmp(par.val, par.min, tol) == 0:
                        param_warnings += f"WARNING: parameter value {par.fullname} is at its minimum boundary {par.min}\n"
                    if sao_fcmp(par.val, par.max, tol) == 0:
                        param_warnings += f"WARNING: parameter value {par.fullname} is at its maximum boundary {par.max}\n"
            if record_steps:
                extended_names = ['nfev', 'statistic'] + names
                dtypes = [int] + [float] * (len(extended_names) - 1)
                imap['record_steps'] = np.array(cb.record_steps,
                                                dtype = [(n, d) for n, d in zip(extended_names, dtypes)])


        output = (status, newpars, fval_new, msg, imap)
        return FitResults(self, output, init_stat, param_warnings.strip("\n"))

    @evaluates_model
    def simulfit(self, *others: Fit) -> FitResults:
        """Fit multiple data sets and models simultaneously.

        The current fit object is combined with the other fit
        objects and a simultaneous fit is made, using the object's
        statistic and optimisation method.

        Parameters
        ----------
        *others : `sherpa.fit.Fit` instances
            The ``data`` and ``model`` attributes of these arguments
            are used, along with those from the object.

        Returns
        -------
        fitres : `FitResults`

        See Also
        --------
        fit

        """
        if len(others) == 0:
            return self.fit()

        fits = (self,) + others
        d = DataSimulFit('simulfit data', tuple(f.data for f in fits))
        m = SimulFitModel('simulfit model', tuple(f.model for f in fits))

        f = Fit(d, m, self.stat, self.method)
        return f.fit()

    @evaluates_model
    def est_errors(self,
                   methoddict: Mapping[str, Any] | None = None,
                   parlist: Sequence[Parameter] | None = None
                   ) -> ErrorEstResults:
        """Estimate errors.

        Calculate the low and high errors for one or more of the
        thawed parameters in the fit.

        Parameters
        ----------
        methoddict : dict or None, optional
            A dictionary mapping from lower-cased method name to
            the associated optimisation method instance to use. This
            is only used if the method is changed, as described in
            the Notes section below.
        parlist : sequence of `sherpa.models.parameter.Parameter` or None, optional
            The names of the parameters for which the errors should
            be calculated. If set to `None` then all the thawed
            parameters are used.

        Returns
        -------
        res : ErrorEstResults

        Raises
        ------
        `sherpa.utils.err.EstErr`
           If any parameter in parlist is not valid (i.e. is not
           thawed or is not a member of the model expression being
           fit), or if the statistic is `~sherpa.stats.LeastSq`,
           or if the reduced chi-square value of the current parameter
           values is larger than the ``max_rstat`` option (for
           chi-square statistics).

        See Also
        --------
        fit

        Notes
        -----
        If a new minimum is found for any parameter then the calculation
        is automatically started for all the parameters using this
        new best-fit location. This can repeat until the ``maxfits``
        option is reached.

        Unless the `~sherpa.estmethods.Covariance` estimator
        is being used, or the ``fast`` option is unset, then the method
        will be changed to `~sherpa.optmethods.NelderMead` (for
        likelihood-based statistics) or `~sherpa.optmethods.LevMar`
        (for chi-square based statistics) whilst calculating the
        errors.
        """

        # Since the set of thawed parameters can change during this
        # loop we need to keep the "original" version for use.
        #
        thawedpars = self.model.get_thawed_pars()

        # Define functions to freeze and thaw a parameter before
        # we call fit function -- projection can call fit several
        # times, for each parameter -- that parameter must be frozen
        # while the others freely vary.
        def freeze_par(pars, parmins, parmaxes, idx):
            # Freeze the indicated parameter; return
            # its place in the list of all parameters,
            # and the current values of the parameters,
            # and the hard mins amd maxs of the parameters
            thawedpars[idx].val = pars[idx]
            thawedpars[idx].frozen = True
            self.current_frozen = idx

            # Identify those parameters that are not frozen.
            keep_pars = np.ones_like(pars)
            keep_pars[idx] = 0
            pars_idx = np.where(keep_pars)

            current_pars = pars[pars_idx]
            current_parmins = parmins[pars_idx]
            current_parmaxes = parmaxes[pars_idx]
            return (current_pars, current_parmins, current_parmaxes)

        def thaw_par(idx):
            if idx < 0:
                return

            thawedpars[idx].frozen = False
            self.current_frozen = -1

        # confidence needs to know which parameter it is working on.
        def get_par_name(idx):
            return thawedpars[idx].fullname

        # Call from a parameter estimation method, to report that
        # limits for a given parameter have been found At present (mid
        # 2023) it looks like lower/upper are both single-element
        # ndarrays, hence the need to convert to a scalar by accessing
        # the first element (otherwise there's a deprecation warning
        # from NumPy 1.25).
        #
        def report_progress(idx, lower, upper):
            if idx < 0:
                return

            name = thawedpars[idx].fullname
            if np.isnan(lower) or np.isinf(lower):
                info("%s \tlower bound: -----", name)
            else:
                info("%s \tlower bound: %g", name, lower[0])
            if np.isnan(upper) or np.isinf(upper):
                info("%s \tupper bound: -----", name)
            else:
                info("%s \tupper bound: %g", name, upper[0])

        # If starting fit statistic is chi-squared or C-stat,
        # can calculate reduced fit statistic -- if it is
        # more than 3, don't bother calling method to estimate
        # parameter limits.

        if type(self.stat) is LeastSq:
            raise EstErr('noerr4least2', type(self.stat).__name__)

        if type(self.stat) is not Cash:
            dep, staterror, syserror = self.data.to_fit(
                self.stat.calc_staterror)

            ndep = _check_length(dep)

            # For chi-squared and C-stat, reduced statistic is
            # statistic value divided by number of degrees of
            # freedom.

            # Degrees of freedom are number of data bins included
            # in fit, minus the number of thawed parameters.
            dof = ndep - len(thawedpars)
            if dof < 1:
                raise EstErr('nodegfreedom')

            if (hasattr(self.estmethod, "max_rstat") and
                    (self.calc_stat() / dof) > self.estmethod.max_rstat):
                raise EstErr('rstat>max', str(self.estmethod.max_rstat))

        # If statistic is chi-squared, change fitting method to
        # Levenberg-Marquardt; else, switch to NelderMead.  (We
        # will do fitting during projection, and therefore don't
        # want to use LM with a stat other than chi-squared).

        # If current method is not LM or NM, warn it is not a good
        # method for estimating parameter limits.
        if (type(self.estmethod) is not Covariance and
                type(self.method) is not NelderMead and
                type(self.method) is not LevMar):
            warning("%s is inappropriate for confidence limit estimation",
                    self.method.name)

        oldmethod = self.method
        if (hasattr(self.estmethod, "fast") and
                bool_cast(self.estmethod.fast) and
                methoddict is not None):
            if isinstance(self.stat, Likelihood):
                if type(self.method) is not NelderMead:
                    self.method = methoddict['neldermead']
                    warning("Setting optimization to %s "
                            "for confidence limit search", self.method.name)
            else:
                if type(self.method) is not LevMar:
                    self.method = methoddict['levmar']
                    warning("Setting optimization to %s "
                            "for confidence limit search", self.method.name)

        # Now, set up before we call the confidence limit function
        # Keep track of starting values, will need to set parameters
        # back to starting values when we are done.
        startpars = self.model.thawedpars
        startsoftmins = self.model.thawedparmins
        startsoftmaxs = self.model.thawedparmaxes
        starthardmins = self.model.thawedparhardmins
        starthardmaxs = self.model.thawedparhardmaxes

        # If restricted to soft_limits, only send soft limits to
        # method, and do not reset model limits
        if bool_cast(self.estmethod.soft_limits):
            starthardmins = self.model.thawedparmins
            starthardmaxs = self.model.thawedparmaxes
        else:
            self.model.thawedparmins = starthardmins
            self.model.thawedparmaxes = starthardmaxs

        self.current_frozen = -1

        # parnums is the list of indices of the thawed parameters
        # we want to visit.  For example, if there are three thawed
        # parameters, and we want to derive limits for only the first
        # and third, then parnums = [0,2].  We construct the list by
        # comparing each parameter in parlist to the thawed model
        # parameters.  (In the default case, when parlist is None,
        # that means get limits for all thawed parameters, so parnums
        # is [0, ... , numpars - 1], if the number of thawed parameters
        # is numpars.)
        if parlist is not None:
            pars = parlist
            allpars = self.model.get_thawed_pars()
            pnums = []
            for p in pars:
                count = 0
                match = False
                for par in allpars:
                    if p is par:
                        pnums.append(count)
                        match = True
                    count = count + 1

                if not match:
                    raise EstErr('noparameter', p.fullname)

            parnums = np.array(pnums)
        else:
            pars = self.model.get_thawed_pars()
            parnums = np.arange(len(startpars))

        # If we are here, we are ready to try to derive confidence limits.
        # General rule:  if failure because a hard limit was hit, find
        # out which parameter it was so we can tell the user.
        # If a new minimum statistic was found, start over, with parameter
        # values that yielded new lower statistic as the new starting point.
        output = None
        results = None
        oldremin = -1.0
        if hasattr(self.estmethod, "remin"):
            oldremin = self.estmethod.remin
        try:
            output = self.estmethod.compute(self._iterfit._get_callback(),
                                            self._iterfit.fit,
                                            pars=self.model.thawedpars,
                                            parmins=startsoftmins,
                                            parmaxes=startsoftmaxs,
                                            parhardmins=starthardmins,
                                            parhardmaxes=starthardmaxs,
                                            limit_parnums=parnums,
                                            freeze_par=freeze_par,
                                            thaw_par=thaw_par,
                                            report_progress=report_progress,
                                            get_par_name=get_par_name)
        except EstNewMin as e:
            # If maximum number of refits has occurred, don't
            # try to reminimize again.
            if (hasattr(self.estmethod, "maxfits") and
                    not (self.refits < (self.estmethod.maxfits - 1))):
                self.refits = 0
                thaw_par(self.current_frozen)
                self.model.thawedpars = startpars
                self.model.thawedparmins = startsoftmins
                self.model.thawedparmaxes = startsoftmaxs
                self.method = oldmethod
                if hasattr(self.estmethod, "remin"):
                    self.estmethod.remin = -1.0
                warning("Maximum number of reminimizations reached")

            # First report results of new fit, then call
            # compute limits for those new best-fit parameters
            for p in pars:
                p.frozen = False
            self.current_frozen = -1

            if e.args:
                # Reset the parameter values to those reported in the
                # exception.
                self.model.thawedpars = e.args[0]

            self.model.thawedparmins = startsoftmins
            self.model.thawedparmaxes = startsoftmaxs
            results = self.fit()
            self.refits = self.refits + 1
            warning("New minimum statistic found while computing "
                    "confidence limits")
            warning("New best-fit parameters:\n%s", results.format())

            # Now, recompute errors for new best-fit parameters
            results = self.est_errors(methoddict, pars)
            self.model.thawedparmins = startsoftmins
            self.model.thawedparmaxes = startsoftmaxs
            self.method = oldmethod
            if hasattr(self.estmethod, "remin"):
                self.estmethod.remin = oldremin
            return results
        except:
            for p in pars:
                p.frozen = False
            self.current_frozen = -1
            self.model.thawedpars = startpars
            self.model.thawedparmins = startsoftmins
            self.model.thawedparmaxes = startsoftmaxs
            self.method = oldmethod
            if hasattr(self.estmethod, "remin"):
                self.estmethod.remin = oldremin
            raise

        for p in pars:
            p.frozen = False

        self.current_frozen = -1
        self.model.thawedpars = startpars
        self.model.thawedparmins = startsoftmins
        self.model.thawedparmaxes = startsoftmaxs
        results = ErrorEstResults(self, output, pars)
        self.method = oldmethod
        if hasattr(self.estmethod, "remin"):
            self.estmethod.remin = oldremin

        return results


# Notebook representation
#
def html_fitresults(fit: FitResults) -> str:
    """Construct the HTML to display the FitResults object."""

    has_covar = fit.covar is not None

    ls = []

    if not fit.succeeded:
        out = '<p class="failed">'
        out += '<strong>The fit failed:</strong> '
        out += fit.message
        out += '.</p>'
        ls.append(out)

    # The parameter values
    #
    header = ['Parameter', 'Best-fit value']
    if has_covar:
        header.append('Approximate error')

    rows: list[tuple] = []
    if has_covar:
        assert fit.covar is not None  # already checked
        for pname, pval, perr in zip(fit.parnames, fit.parvals,
                                     np.sqrt(fit.covar.diagonal())):
            rows.append((pname, f'{pval:12g}',
                         f'&#177; {perr:12g}'))
    else:
        for pname, pval in zip(fit.parnames, fit.parvals):
            rows.append((pname, f'{pval:12g}'))

    out = formatting.html_table(header, rows, classname='fit',
                                rowcount=False,
                                summary='Fit parameters')
    ls.append(out)

    # Metadata/summary
    #
    meta = []

    if fit.datasets is not None:
        key = 'Dataset'
        if len(fit.datasets) > 1:
            key += 's'

        meta.append((key,
                     ','.join([str(d) for d in fit.datasets])))

    rows = [('Method', 'methodname', False),
            ('Statistic', 'statname', False)]

    if fit.itermethodname != 'none':
        # TODO: what label
        rows.append(('Iteration method', 'itermethodname', False))

    rows.append(('Final statistic', 'statval', True))
    if fit.nfev is not None:
        rows.append(('Number of evaluations', 'nfev', False))

    if fit.rstat is not None:
        rows.append(('Reduced statistic', 'rstat', True))
    if fit.qval is not None:
        rows.append(('Probability (Q-value)', 'qval', True))

    rows.extend([('Initial statistic', 'istatval', True),
                 ('&#916; statistic', 'dstatval', True),
                 ('Number of data points', 'numpoints', False),
                 ('Degrees of freedom', 'dof', False)])

    for lbl, field, is_float in rows:
        val = getattr(fit, field)
        if is_float:
            val = f'{val:g}'

        meta.append((lbl, val))

    ls.append(formatting.html_section(meta, summary='Summary'))

    return formatting.html_from_sections(fit, ls)


def html_errresults(errs: ErrorEstResults) -> str:
    """Construct the HTML to display the ErrorEstResults object."""

    ls = []

    # The error estimates
    #
    header = ['Parameter', 'Best-fit value', 'Lower Bound',
              'Upper Bound']

    rows = []

    def display(limit):
        """Display the limit

        Should we try to HTML-ify the open interval?
        """

        if limit is None:
            return '-----'

        if is_iterable(limit):
            return list_to_open_interval(limit)

        return f'{limit:12g}'

    for pname, pval, pmin, pmax in zip(errs.parnames, errs.parvals, errs.parmins, errs.parmaxes):
        rows.append((pname, f'{pval:12g}',
                     display(pmin), display(pmax)))

    summary = f'{errs.methodname} {errs.sigma:g}&#963; ({errs.percent:2g}%)'
    summary += ' bounds'

    out = formatting.html_table(header, rows,
                                rowcount=False,
                                summary=summary)
    ls.append(out)

    # Metadata/summary
    #
    meta = []

    if errs.datasets is not None:
        key = 'Dataset'
        if len(errs.datasets) > 1:
            key += 's'

        meta.append((key,
                     ','.join([str(d) for d in errs.datasets])))

    rows: list[tuple[str, str]] = []
    if errs.iterfitname is not None and errs.iterfitname != 'none':
        rows.append(('Iteration method', 'iterfitname'))

    rows.extend([('Fitting Method', 'fitname'),
                 ('Statistic', 'statname')])

    for lbl, field in rows:
        meta.append((lbl, getattr(errs, field)))

    ls.append(formatting.html_section(meta, summary='Summary'))
    return formatting.html_from_sections(errs, ls)


def html_statinfo(stats: StatInfoResults) -> str:
    """Construct the HTML to display the StatInfoResults object."""

    meta = []

    # This differs from the format method, both because of how the
    # information is presented (a row for background separate from
    # the data, which makes it easier to handle), but also because
    # it doesn't assume singular source and background values (if
    # both are set). It is not clear what combinations are supported.
    #
    if stats.ids is not None:

        key = 'Dataset'
        if len(stats.ids) > 1:
            key += 's'
            val = str(stats.ids).strip("()")
        else:
            val = stats.ids[0]

        meta.append((key, val))

        if stats.bkg_ids is not None:
            # If there are multiple source datasets then the
            # background ids would need to be mapped to the
            # source dataset, but leave that for a later revision,
            # as it isn't clear it is supported.
            #
            key = 'Background'
            if len(stats.bkg_ids) > 1:
                key += 's'
                val = str(stats.bkg_ids).strip("()")
            else:
                val = stats.bkg_ids[0]

            meta.append((key, val))

    rows = [('Statistic', 'statname', False),
            ('Value', 'statval', True),
            ('Number of points', 'numpoints', False),
            ('Degrees of freedom', 'dof', False)]

    if stats.rstat is not None:
        rows.append(('Reduced statistic', 'rstat', True))
    if stats.qval is not None:
        rows.append(('Probability (Q-value)', 'qval', True))

    for lbl, field, is_float in rows:
        val = getattr(stats, field)
        if is_float:
            val = f'{val:g}'

        meta.append((lbl, val))

    ls = [formatting.html_section(meta, open_block=True,
                                  summary='Statistics summary')]
    return formatting.html_from_sections(stats, ls)
