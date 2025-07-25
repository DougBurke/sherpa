#
#  Copyright (C) 2007, 2015, 2018, 2020, 2021, 2023 - 2025
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

"""Optimization classes.

The `OptMethod` class provides an interface to a number of optimisers.
When creating an optimizer an optional name can be added; this name is
only used in string representations of the class:

>>> from sherpa.optmethods import NelderMead
>>> opt = NelderMead()
>>> print(opt)
name         = simplex
ftol         = 1.1920928955078125e-07
maxfev       = None
initsimplex  = 0
finalsimplex = 9
step         = None
iquad        = 1
verbose      = 0
reflect      = True

A model is fit by providing the ``fit`` method a callback, the starting
point (parameter values), and parameter ranges. The callback should
match the `StatFunc` type::

    callback(pars)

and return the statistic value to minimise along with the per-bin
statistic values (note that per-bin here refers to the independent
axis of the data being fit, and not the number of parameters being
fit).

.. versionchanged:: 4.18.0
   The callback is no-longer sent extra information (that is,
   the statargs and statkwargs values) and is just sent an array
   of parameter values.

Notes
-----

Each optimizer has certain classes of problem where it is more, or
less, successful. For instance, the `NelderMead` class should
only be used with chi-square based statistics.

Examples
--------

Using Sherpa classes for data, models, and statistics we can create a
callback, in this case using a least-squared statistic to fit a
constant model to a 1D dataset (we do not need to send any extra
arguments to the callback other than the parameter values in this
case):

>>> import numpy as np
>>> from sherpa.data import Data1D
>>> from sherpa.models.basic import Const1D
>>> from sherpa.stats import LeastSq
>>> x = np.asarray([1, 2, 5])
>>> y = np.asarray([3, 2, 7])
>>> d = Data1D('data', x, y)
>>> mdl = Const1D()
>>> stat = LeastSq()
>>> def cb(pars):
...     mdl.thawedpars = pars
...     return stat.calc_stat(d, mdl)

We can check the model before the optimisaton run:

>>> print(mdl)
const1d
   Param        Type          Value          Min          Max      Units
   -----        ----          -----          ---          ---      -----
   const1d.c0   thawed            1 -3.40282e+38  3.40282e+38

The model can be fit using the ``fit`` method:

>>> from sherpa.optmethods import NelderMead
>>> opt = NelderMead()
>>> res = opt.fit(cb, mdl.thawedpars, mdl.thawedparmins, mdl.thawedparmaxes)

The return from ``fit`` is a tuple where the first element indicates
whether the fit was successful, then the best-fit parameters, the
best-fit statistic, a string message, along with a dictionary
depending on the optimiser:

>>> print(res)
(True, array([4.]), 14.0, 'Optimization terminated successfully', {'info': True, 'nfev': 98})
>>> print(f"Best-fit value: {res[1][0]}")
Best-fit value: 4.0

We can see that the model has been updated thanks to the use of
``cb``, which sets the ``thawedpars`` attribute of ``mdl``:

>>> print(mdl)
const1d
   Param        Type          Value          Min          Max      Units
   -----        ----          -----          ---          ---      -----
   const1d.c0   thawed            4 -3.40282e+38  3.40282e+38

"""

import logging
from typing import Any

import numpy as np

from sherpa.utils import NoNewAttributesAfterInit, \
    get_keyword_names, get_keyword_defaults, print_fields
from sherpa.utils.types import ArrayType, OptFunc, OptReturn, StatFunc

from .optfcts import grid_search, lmdif, montecarlo, neldermead


warning = logging.getLogger(__name__).warning


__all__ = ('GridSearch', 'OptMethod', 'LevMar', 'MonCar', 'NelderMead')


class OptMethod(NoNewAttributesAfterInit):
    """Base class for the optimisers.

    Parameters
    ----------
    name : str
       The name of the optimiser.
    optfunc : function
       The function which optimises the model: its arguments are
       a function which evaluates the statistic given a list of parameter
       values, the starting parameters, minima, and maxima, followed
       by keyword arguments matching the configuration data.

    Notes
    -----

    The optfunc argument is used to define the configuration
    options: they are taken from the keyword arguments and used
    to create the `default_config` dictionary which is then
    used to create the user-editable `config` field.

    The optfunc function must accept the positional arguments::

        fcn:  OptFunc
        x0:   ArrayType
        xmin: ArrayType
        xmax: ArrayType

    and the remaining arguments are sent in as keyword arguments, and
    so can be specific to the optimization function. The x0, xmin, and
    xmax values specify the starting values and their minimum and
    maximum limits; they are intended to be sent in as 1D numeric
    arrays.

    The function returns the statistic value and per-bin statistic
    values for the given values.

    """

    def __init__(self,
                 name: str,
                 optfunc: OptFunc
                 ) -> None:
        self.name = name
        self._optfunc = optfunc
        self.config: dict[str, Any] = self.default_config
        super().__init__()

    # Allow direct access to the configuration options.
    #
    def __getattr__(self, name: str) -> Any:
        if name in self.__dict__.get('config', ()):
            return self.config[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name: str, val: Any) -> None:
        if name in self.__dict__.get('config', ()):
            self.config[name] = val
        else:
            NoNewAttributesAfterInit.__setattr__(self, name, val)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} optimization method instance '{self.name}'>"

    # Need to support users who have pickled sessions < CIAO 4.2
    # TODO: can this be removed as CIAO 4.2 was a long time ago?
    #
    def __setstate__(self, state):
        new_config = get_keyword_defaults(state.get('_optfunc'))
        old_config = state.get('config', {})

        # remove old kw args from opt method dict
        for key in old_config.keys():
            if key not in new_config:
                old_config.pop(key)

        # add new kw args with defaults
        for key, val in new_config.items():
            if key not in old_config:
                old_config[key] = val

        self.__dict__.update(state)

    def __str__(self) -> str:
        names = ['name']
        names.extend(get_keyword_names(self._optfunc))
        # names.remove('full_output')
        # Add the method's name to printed output
        # Don't add to self.config b/c name isn't a
        # fit function config setting
        add_name_config = {}
        add_name_config['name'] = self.name
        add_name_config.update(self.config)
        return print_fields(names, add_name_config)

    def _get_default_config(self) -> dict[str, Any]:
        return get_keyword_defaults(self._optfunc)

    default_config = property(_get_default_config,
                              doc='The default settings for the optimiser.')

    def fit(self,
            statfunc: StatFunc,
            pars: ArrayType,
            parmins: ArrayType,
            parmaxes: ArrayType,
            statargs: Any = None,
            statkwargs: Any = None
            ) -> OptReturn:
        """Run the optimiser.

        .. versionchanged:: 4.18.0
           The statargs and statkwargs arguments are now ignored.

        .. versionchanged:: 4.16.0
           The statkwargs argument now defaults to None rather than {}.

        Parameters
        ----------
        statfunc : function
           Given a list of parameter values as the first argument and,
           as the remaining positional arguments, `statargs` and
           `statkwargs` as keyword arguments, return the statistic
           value.
        pars : sequence
           The start position of the model parameter values.
        parmins : sequence
           The minimum allowed values for each model parameter. This
           must match the length of `pars`.
        parmaxes : sequence
           The maximum allowed values for each model parameter. This
           must match the length of `pars`.
        statargs : optional
           This is currently unused.
        statkwargs : optional
           This is currently unused.

        Returns
        -------
        newpars : tuple
           The tuple contains: boolean indicating whether the
           optimization succeeded or not, the best fit parameters as a
           NumPy array, the statistic value at the best-fit location,
           a string message indicating the status, and a dictionary
           containing information about the optimisation (this depends
           on the optimiser).

        """

        if statargs is not None or statkwargs is not None:
            warning("statargs/kwargs set but values unused")

        output = self._optfunc(statfunc, pars, parmins, parmaxes,
                               **self.config)
        (success, pars, fval, msg, imsg) = output
        if not success:
            warning('fit failed: %s', msg)

        # Ensure that the best-fit parameters are in an array.  (If
        # there's only one, it might be returned as a bare float. This
        # should be reviewed to check if it still happens).
        #
        npars = np.asarray(pars).ravel()
        return (success, npars, fval, msg, imsg)


# ## DOC-TODO: better description of the sequence argument; what happens
# ##           with multiple free parameters.
# ## DOC-TODO: what does the method attribute take: string or class instance?
# ## DOC-TODO: it looks like there's no error checking on the method attribute
class GridSearch(OptMethod):
    """Grid Search optimization method.

    This method evaluates the fit statistic for each point in the
    parameter space grid; the best match is the grid point with the
    lowest value of the fit statistic. It is intended for use with
    template models as it is very inefficient for general models.

    Attributes
    ----------
    num : int
       The size of the grid for each parameter when `sequence` is
       `None`, so ``npar^num`` fits will be evaluated, where `npar` is
       the number of free parameters. The grid spacing is uniform.
    sequence : sequence of numbers or `None`
       The list through which to evaluate. Leave as `None` to use
       a uniform grid spacing as determined by the `num` attribute.
    numcores : int or `None`
       The number of CPU cores to use. The default is `1` and a
       value of `None` will use all the cores on the machine.
    maxfev : int or `None`
       The `maxfev` attribute if `method` is not `None`.
    ftol : number
       The `ftol` attribute if `method` is not `None`.
    method : str or `None`
       The optimization method to use to refine the best-fit
       location found using the grid search. If `None` then
       this step is not run.
    verbose: int
       The amount of information to print during the fit. The default
       is `0`, which means no output.

    """

    def __init__(self, name: str = 'gridsearch') -> None:
        super().__init__(name=name, optfunc=grid_search)


"""
  LMDIF.

                                                                 Page 1

               Documentation for MINPACK subroutine LMDIF

                        Double precision version

                      Argonne National Laboratory

         Burton S. Garbow, Kenneth E. Hillstrom, Jorge J. More

                               March 1980


 1. Purpose.

       The purpose of LMDIF is to minimize the sum of the squares of M
       nonlinear functions in N variables by a modification of the
       Levenberg-Marquardt algorithm.  The user must provide a subrou-
       tine which calculates the functions.  The Jacobian is then cal-
       culated by a forward-difference approximation.


 2. Subroutine and type statements.

       SUBROUTINE LMDIF(FCN,M,N,X,FVEC,FTOL,XTOL,GTOL,MAXFEV,EPSFCN,
      *                 DIAG,MODE,FACTOR,NPRINT,INFO,NFEV,FJAC,LDFJAC,
      *                 IPVT,QTF,WA1,WA2,WA3,WA4)
       INTEGER M,N,MAXFEV,MODE,NPRINT,INFO,NFEV,LDFJAC
       INTEGER IPVT(N)
       DOUBLE PRECISION FTOL,XTOL,GTOL,EPSFCN,FACTOR
       DOUBLE PRECISION X(N),FVEC(M),DIAG(N),FJAC(LDFJAC,N),QTF(N),
      *                 WA1(N),WA2(N),WA3(N),WA4(M)
       EXTERNAL FCN


 3. Parameters.

       Parameters designated as input parameters must be specified on
       entry to LMDIF and are not changed on exit, while parameters
       designated as output parameters need not be specified on entry
       and are set to appropriate values on exit from LMDIF.

       FCN is the name of the user-supplied subroutine which calculates
         the functions.  FCN must be declared in an EXTERNAL statement
         in the user calling program, and should be written as follows.

         SUBROUTINE FCN(M,N,X,FVEC,IFLAG)
         INTEGER M,N,IFLAG
         DOUBLE PRECISION X(N),FVEC(M)
         ----------
         CALCULATE THE FUNCTIONS AT X AND
         RETURN THIS VECTOR IN FVEC.
         ----------
         RETURN
         END


                                                                 Page 2

         The value of IFLAG should not be changed by FCN unless the
         user wants to terminate execution of LMDIF.  In this case set
         IFLAG to a negative integer.

       M is a positive integer input variable set to the number of
         functions.

       N is a positive integer input variable set to the number of
         variables.  N must not exceed M.

       X is an array of length N.  On input X must contain an initial
         estimate of the solution vector.  On output X contains the
         final estimate of the solution vector.

       FVEC is an output array of length M which contains the functions
         evaluated at the output X.

       FTOL is a nonnegative input variable.  Termination occurs when
         both the actual and predicted relative reductions in the sum
         of squares are at most FTOL.  Therefore, FTOL measures the
         relative error desired in the sum of squares.  Section 4 con-
         tains more details about FTOL.

       XTOL is a nonnegative input variable.  Termination occurs when
         the relative error between two consecutive iterates is at most
         XTOL.  Therefore, XTOL measures the relative error desired in
         the approximate solution.  Section 4 contains more details
         about XTOL.

       GTOL is a nonnegative input variable.  Termination occurs when
         the cosine of the angle between FVEC and any column of the
         Jacobian is at most GTOL in absolute value.  Therefore, GTOL
         measures the orthogonality desired between the function vector
         and the columns of the Jacobian.  Section 4 contains more
         details about GTOL.

       MAXFEV is a positive integer input variable.  Termination occurs
         when the number of calls to FCN is at least MAXFEV by the end
         of an iteration.

       EPSFCN is an input variable used in determining a suitable step
         for the forward-difference approximation.  This approximation
         assumes that the relative errors in the functions are of the
         order of EPSFCN.  If EPSFCN is less than the machine preci-
         sion, it is assumed that the relative errors in the functions
         are of the order of the machine precision.

       DIAG is an array of length N.  If MODE = 1 (see below), DIAG is
         internally set.  If MODE = 2, DIAG must contain positive
         entries that serve as multiplicative scale factors for the
         variables.

       MODE is an integer input variable.  If MODE = 1, the variables
         will be scaled internally.  If MODE = 2, the scaling is


                                                                 Page 3

         specified by the input DIAG.  Other values of MODE are equiva-
         lent to MODE = 1.

       FACTOR is a positive input variable used in determining the ini-
         tial step bound.  This bound is set to the product of FACTOR
         and the Euclidean norm of DIAG*X if nonzero, or else to FACTOR
         itself.  In most cases FACTOR should lie in the interval
         (.1,100.).  100. is a generally recommended value.

       NPRINT is an integer input variable that enables controlled
         printing of iterates if it is positive.  In this case, FCN is
         called with IFLAG = 0 at the beginning of the first iteration
         and every NPRINT iterations thereafter and immediately prior
         to return, with X and FVEC available for printing.  If NPRINT
         is not positive, no special calls of FCN with IFLAG = 0 are
         made.

       INFO is an integer output variable.  If the user has terminated
         execution, INFO is set to the (negative) value of IFLAG.  See
         description of FCN.  Otherwise, INFO is set as follows.

         INFO = 0  Improper input parameters.

         INFO = 1  Both actual and predicted relative reductions in the
                   sum of squares are at most FTOL.

         INFO = 2  Relative error between two consecutive iterates is
                   at most XTOL.

         INFO = 3  Conditions for INFO = 1 and INFO = 2 both hold.

         INFO = 4  The cosine of the angle between FVEC and any column
                   of the Jacobian is at most GTOL in absolute value.

         INFO = 5  Number of calls to FCN has reached or exceeded
                   MAXFEV.

         INFO = 6  FTOL is too small.  No further reduction in the sum
                   of squares is possible.

         INFO = 7  XTOL is too small.  No further improvement in the
                   approximate solution X is possible.

         INFO = 8  GTOL is too small.  FVEC is orthogonal to the
                   columns of the Jacobian to machine precision.

         Sections 4 and 5 contain more details about INFO.

       NFEV is an integer output variable set to the number of calls to
         FCN.

       FJAC is an output M by N array.  The upper N by N submatrix of
         FJAC contains an upper triangular matrix R with diagonal ele-
         ments of nonincreasing magnitude such that


                                                                 Page 4

                T     T           T
               P *(JAC *JAC)*P = R *R,

         where P is a permutation matrix and JAC is the final calcu-
         lated J

"""


class LevMar(OptMethod):
    """Levenberg-Marquardt optimization method.

    The Levenberg-Marquardt method is an interface to the MINPACK
    subroutine lmdif to find the local minimum of nonlinear least
    squares functions of several variables by a modification of the
    Levenberg-Marquardt algorithm [1]_.

    Attributes
    ----------
    ftol : number
       The function tolerance to terminate the search for the minimum;
       the default is FLT_EPSILON ~ 1.19209289551e-07, where
       FLT_EPSILON is the smallest number x such that ``1.0 != 1.0 +
       x``. The conditions are satisfied when both the actual and
       predicted relative reductions in the sum of squares are, at
       most, ftol.
    xtol : number
       The relative error desired in the approximate solution; default
       is FLT_EPSILON ~ 1.19209289551e-07, where FLT_EPSILON
       is the smallest number x such that ``1.0 != 1.0 + x``. The
       conditions are satisfied when the relative error between two
       consecutive iterates is, at most, `xtol`.
    gtol : number
       The orthogonality desired between the function vector and the
       columns of the jacobian; default is FLT_EPSILON ~
       1.19209289551e-07, where FLT_EPSILON is the smallest number x
       such that ``1.0 != 1.0 + x``. The conditions are satisfied when
       the cosine of the angle between fvec and any column of the
       jacobian is, at most, `gtol` in absolute value.
    maxfev : int or `None`
       The maximum number of function evaluations; the default value
       of `None` means to use ``1024 * n``, where `n` is the number of
       free parameters.
    epsfcn : number
       This is used in determining a suitable step length for the
       forward-difference approximation; default is FLT_EPSILON
       ~ 1.19209289551e-07, where FLT_EPSILON is the smallest number
       x such that ``1.0 != 1.0 + x``. This approximation assumes that
       the relative errors in the functions are of the order of
       `epsfcn`. If `epsfcn` is less than the machine precision, it is
       assumed that the relative errors in the functions are of the
       order of the machine precision.
    factor : int
       Used in determining the initial step bound; default is 100. The
       initial step bound is set to the product of `factor` and the
       euclidean norm of diag*x if nonzero, or else to factor itself.
       In most cases, `factor` should be from the interval (.1,100.).
    numcores : int
       The number of CPU cores to use. The default is `1`.
    verbose: int
       The amount of information to print during the fit. The default
       is `0`, which means no output.

    References
    ----------

    .. [1] J.J. More, "The Levenberg Marquardt algorithm:
           implementation and theory," in Lecture Notes in Mathematics
           630: Numerical Analysis, G.A. Watson (Ed.),
           Springer-Verlag: Berlin, 1978, pp.105-116.

        """
    def __init__(self, name: str = 'levmar') -> None:
        super().__init__(name=name, optfunc=lmdif)


class MonCar(OptMethod):
    """Monte Carlo optimization method.

    This is an implementation of the differential-evolution algorithm
    from Storn and Price (1997) [1]_. A population of fixed size -
    which contains n-dimensional vectors, where n is the number of
    free parameters - is randomly initialized.  At each iteration, a
    new n-dimensional vector is generated by combining vectors from
    the pool of population, the resulting trial vector is selected if
    it lowers the objective function.

    Attributes
    ----------
    ftol : number
       The function tolerance to terminate the search for the minimum;
       the default is sqrt(DBL_EPSILON) ~ 1.19209289551e-07, where
       DBL_EPSILON is the smallest number x such that ``1.0 != 1.0 +
       x``.
    maxfev : int or `None`
       The maximum number of function evaluations; the default value
       of `None` means to use ``8192 * n``, where `n` is the number of
       free parameters.
    verbose: int
       The amount of information to print during the fit. The default
       is `0`, which means no output.
    seed : int
       The seed for the random number generator.
    population_size : int or `None`
       The population of potential solutions is allowed to evolve to
       search for the minimum of the fit statistics. The trial
       solution is randomly chosen from a combination from the current
       population, and it is only accepted if it lowers the
       statistics.  A value of `None` means to use a value ``16 * n``,
       where `n` is the number of free parameters.
    xprob : num
       The crossover probability should be within the range [0.5,1.0];
       default value is 0.9. A high value for the crossover
       probability should result in a faster convergence rate;
       conversely, a lower value should make the differential
       evolution method more robust.
    weighting_factor: num
       The weighting factor should be within the range [0.5, 1.0];
       default is 0.8. Differential evolution is more sensitive to the
       weighting_factor then the xprob parameter. A lower value for
       the weighting_factor, coupled with an increase in the
       population_size, gives a more robust search at the cost of
       efficiency.
    numcores : int
       The number of CPU cores to use. The default is `1`.

    References
    ----------

    .. [1] Storn, R. and Price, K. "Differential Evolution: A Simple
           and Efficient Adaptive Scheme for Global Optimization over
           Continuous Spaces." J. Global Optimization 11, 341-359,
           1997.
           https://cse.engineering.nyu.edu/~mleung/CS909/s04/Storn95-012.pdf

    """

    def __init__(self, name: str = 'moncar') -> None:
        super().__init__(name=name, optfunc=montecarlo)


# ## DOC-TODO: finalximplex=4 and 5 list the same conditions, it is likely
# ##           a cut-n-paste error, so what is the correct description?
class NelderMead(OptMethod):
    r"""Nelder-Mead Simplex optimization method.

    The Nelder-Mead Simplex algorithm, devised by J.A. Nelder and
    R. Mead [1]_, is a direct search method of optimization for
    finding a local minimum of an objective function of several
    variables. The implementation of the Nelder-Mead Simplex algorithm is
    a variation of the algorithm outlined in [2]_ and [3]_. As noted,
    terminating the simplex is not a simple task:

    "For any non-derivative method, the issue of termination is
    problematical as well as highly sensitive to problem scaling.
    Since gradient information is unavailable, it is provably
    impossible to verify closeness to optimality simply by sampling f
    at a finite number of points.  Most implementations of direct
    search methods terminate based on two criteria intended to reflect
    the progress of the algorithm: either the function values at the
    vertices are close, or the simplex has become very small."

    "Either form of termination-close function values or a small
    simplex-can be misleading for badly scaled functions."

    Attributes
    ----------
    ftol : number
       The function tolerance to terminate the search for the minimum;
       the default is sqrt(DBL_EPSILON) ~ 1.19209289551e-07, where
       DBL_EPSILON is the smallest number x such that ``1.0 != 1.0 +
       x``.
    maxfev : int or `None`
       The maximum number of function evaluations; the default value
       of `None` means to use ``1024 * n``, where `n` is the number of
       free parameters.
    initsimplex : int
       Dictates how the non-degenerate initial simplex is to be
       constructed.  Default is `0`; see the "cases for initsimplex"
       section below for details.
    finalsimplex : int
       At each iteration, a combination of one of the following
       stopping criteria is tested to see if the simplex has converged
       or not.  Full details are in the "cases for finalsimplex"
       section below.
    step : array of number or `None`
       A list of length `n` (number of free parameters) to initialize
       the simplex; see the `initsimplex` for details. The default of
       `None` means to use a step of 0.4 for each free parameter.
    iquad : int
       A boolean flag which indicates whether a fit to a quadratic
       surface is done.  If iquad is set to `1` (the default) then a
       fit to a quadratic surface is done; if iquad is set to `0` then
       the quadratic surface fit is not done.  If the fit to the
       quadratic surface is not positive semi-definitive, then the
       search terminated prematurely.  The code to fit the quadratic
       surface was written by D. E. Shaw, CSIRO, Division of
       Mathematics & Statistics, with amendments by
       R. W. M. Wedderburn, Rothamsted Experimental Station, and Alan
       Miller, CSIRO, Division of Mathematics & Statistics.  See also
       [1]_.
    verbose : int
       The amount of information to print during the fit. The default
       is `0`, which means no output.
    reflect : bool
       When a parameter exceeds a limit should the parameter be
       reflected, so moved back within bounds (`True`, the default) or
       should the model evaluation return DBL_MAX, causing the current
       set of parameters to be excluded from the simplex.

    Notes
    -----

    The `initsimplex` option determines how the non-degenerate initial
    simplex is to be constructed:

    - when `initsimplex` is `0`:

      Then x_(user_supplied) is one of the vertices of the simplex.
      The other `n` vertices are::

        for ( int i = 0; i &lt; n; ++i ) {
          for ( int j = 0; j &lt; n; ++j )
            x[ i + 1 ][ j ] = x_[ j ];
            x[ i + 1 ][ i ] = x_[ i ] + step[ i ];
        }

      where step[i] is the ith element of the option step.

    - if `initsimplex` is `1`:

      Then x_(user_supplied) is one of the vertices of the simplex.
      The other `n` vertices are::

                    { x_[j] + pn,   if i - 1 != j
                    {
        x[i][j]  =  {
                    {
                    { x_[j] + qn,   otherwise

      for 1 <= i <= n, 0 <= j < n and::

        pn = ( sqrt( n + 1 ) - 1 + n ) / ( n * sqrt(2) )
        qn = ( sqrt( n + 1 ) - 1 ) / ( n * sqrt(2) )

    The `finalsimplex` option determines whether the simplex has
    converged:

    - case a (if the max length of the simplex is small enough)::

        max( | x_i - x_0 | ) <= ftol max( 1, | x_0 | )
        1 <= i <= n

    - case b (if the standard deviation the simplex is < `ftol`)::

         n           -   2
        ===   ( f  - f )
        \        i                    2
        /     -----------     <=  ftol
        ====   sqrt( n )
        i = 0

    - case c (if the function values are close enough)::

        f_0  < f_(n-1)     within ftol

    The combination of the above stopping criteria are:

    - case 0: same as case a

    - case 1: case a, case b and case c have to be met

    - case 2: case a and either case b or case c have to be met.

    The `finalsimplex` value controls which of these criteria need to
    hold:

    - if ``finalsimplex=0`` then convergence is assumed if case 1 is met.

    - if ``finalsimplex=1`` then convergence is assumed if case 2 is met.

    - if ``finalsimplex=2`` then convergence is assumed if case 0 is met
      at two consecutive iterations.

    - if ``finalsimplex=3`` then convergence is assumed if case 0 then
      case 1 are met on two consecutive iterations.

    - if ``finalsimplex=4`` then convergence is assumed if case 0 then
      case 1 then case 0 are met on three consecutive iterations.

    - if ``finalsimplex=5`` then convergence is assumed if case 0 then
      case 1 then case 0 are met on three consecutive iterations.

    - if ``finalsimplex=6`` then convergence is assumed if case 1 then
      case 1 then case 0 are met on three consecutive iterations.

    - if ``finalsimplex=7`` then convergence is assumed if case 2 then
      case 1 then case 0 are met on three consecutive iterations.

    - if ``finalsimplex=8`` then convergence is assumed if case 0 then
      case 2 then case 0 are met on three consecutive iterations.

    - if ``finalsimplex=9`` then convergence is assumed if case 0 then
      case 1 then case 1 are met on three consecutive iterations.

    - if ``finalsimplex=10`` then convergence is assumed if case 0 then
      case 2 then case 1 are met on three consecutive iterations.

    - if ``finalsimplex=11`` then convergence is assumed if case 1 is
      met on three consecutive iterations.

    - if ``finalsimplex=12`` then convergence is assumed if case 1 then
      case 2 then case 1 are met on three consecutive iterations.

    - if ``finalsimplex=13`` then convergence is assumed if case 2 then
      case 1 then case 1 are met on three consecutive iterations.

    - otherwise convergence is assumed if case 2 is met on three
      consecutive iterations.

    References
    ----------

    .. [1] "A simplex method for function minimization", J.A. Nelder
           and R. Mead (Computer Journal, 1965, vol 7, pp 308-313)
           https://doi.org/10.1093%2Fcomjnl%2F7.4.308

    .. [2] "Convergence Properties of the Nelder-Mead Simplex
           Algorithm in Low Dimensions", Jeffrey C. Lagarias, James
           A. Reeds, Margaret H. Wright, Paul E. Wright , SIAM Journal
           on Optimization, Vol. 9, No. 1 (1998), pages 112-147.
           https://jasoncantarella.com/downloads/SJE000112.pdf

    .. [3] "Direct Search Methods: Once Scorned, Now Respectable"
           Wright, M. H. (1996) in Numerical Analysis 1995
           (Proceedings of the 1995 Dundee Biennial Conference in
           Numerical Analysis, D.F. Griffiths and G.A. Watson, eds.),
           191-208, Addison Wesley Longman, Harlow, United Kingdom.
           https://bemlar.ism.ac.jp/zhuang/Refs/Refs/wright1995numana.pdf

    """
    def __init__(self, name: str = 'simplex') -> None:
        super().__init__(name=name, optfunc=neldermead)
