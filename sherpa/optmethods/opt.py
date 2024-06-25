#
#  Copyright (C) 2019 - 2021, 2023, 2024
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

from typing import Callable, Optional

import numpy as np

from sherpa.utils import Knuth_close, FuncCounter
from sherpa.utils.parallel import multi, context, run_tasks
from sherpa.utils.random import uniform
from sherpa.utils.types import ArrayType


__all__ = ('Opt', 'MyNcores', 'SimplexRandom', 'SimplexNoStep',
           'SimplexStep')


FUNC_MAX = np.finfo(np.float64).max


# import autograd.numpy as np
# from autograd import hessian
# from numpy.linalg.linalg import LinAlgError
# def autograd_covar(func, par):
#     try:
#         hess = hessian(func)(par)
#         result = 2.0 * np.linalg.inv(hess)
#         return result
#     except LinAlgError:
#         return None

class MyNcores:

    def __init__(self):
        if multi is False:
            raise TypeError("multicores not available")

    def calc(self, funcs, numcores, *args, **kwargs):

        for func in funcs:
            if not callable(func):
                raise TypeError(f"input func '{repr(func)}' is not callable")

        # TODO: the numcores argument is currently unused.
        #

        # See sherpa.utils.parallel for the logic used here.
        manager = context.Manager()
        out_q = manager.Queue()
        err_q = manager.Queue()
        procs = [context.Process(target=self.my_worker,
                                 args=(func, ii, out_q, err_q) + args)
                 for ii, func in enumerate(funcs)]

        return run_tasks(procs, err_q, out_q)

    def my_worker(self, opt, idval, out_q, err_q, *args):
        raise NotImplementedError("my_worker has not been implemented")


class Opt:
    """Base optimisation class.

    .. versionchanged:: 4.17.0
       The class structure has been changed (e.g. `nfev` is now a
       scalar and not a single-element list), and the xmin and xmax
       fields are now required.

    """

    def __init__(self,
                 func: Callable[..., float],
                 xmin: ArrayType,
                 xmax: ArrayType
                 ) -> None:
        self.npar = len(xmin)
        self.xmin = np.asarray(xmin)
        self.xmax = np.asarray(xmax)
        self.func_count = FuncCounter(func)
        self.func = self.func_bounds(self.func_count)

    @property
    def nfev(self) -> int:
        return self.func_count.nfev

    def _outside_limits(self, x: np.ndarray) -> bool:
        return bool(np.any(x < self.xmin) or np.any(x > self.xmax))

    def func_bounds(self,
                    func: Callable[..., float]
                    ) -> Callable[..., float]:
        """An infinite-well potential.

        Ensure that the parameter values are bounded by the xmin,xmax
        values by returning a very-large value if they fall outside.
        """

        def func_bounds_wrapper(x, *args):
            if self._outside_limits(x):
                return FUNC_MAX

            return func(x, *args)

        return func_bounds_wrapper


class SimplexBase:

    def __init__(self, func, npop, xpar, xmin, xmax, step, seed,
                 factor, rng=None):
        self.func = func
        self.xmin = xmin
        self.xmax = xmax
        self.npar = len(xpar)
        self.rng = rng
        self.simplex = self.init(npop=npop, xpar=xpar, step=step,
                                 seed=seed, factor=factor)

    def __getitem__(self, index):
        return self.simplex[index]

    def __setitem__(self, index, val):
        self.simplex[index] = val

    def calc_centroid(self):
        return np.mean(self.simplex[:-1, :], 0)

    def check_convergence(self, ftol, method):

        def are_func_vals_close_enough():
            smallest_fct_val = self.simplex[0, -1]
            largest_fct_val = self.simplex[-1, -1]
            return Knuth_close(smallest_fct_val, largest_fct_val,
                               ftol)

        def is_fct_stddev_small_enough():
            fval_std = np.std([col[-1] for col in self.simplex])
            return fval_std < ftol

        def is_max_length_small_enough():
            """

               max  || x  - x  || <= tol max(1.0, || x ||)
                        i    0                         0

            where 1 <= i <= n"""

            max_xi_x0 = -1.0
            x0 = self.simplex[0, :-1]

            npar_plus_1 = len(x0) + 1
            for ii in range(1, npar_plus_1):
                xi = self.simplex[ii, :-1]
                xi_x0 = xi - x0
                max_xi_x0 = max(max_xi_x0, np.dot(xi_x0, xi_x0))
            return max_xi_x0 <= ftol * max(1.0, np.dot(x0, x0))

        if 0 == method:
            if is_max_length_small_enough():
                return True
        elif 2 == method:
            if not is_max_length_small_enough():
                return False
            stddev = is_fct_stddev_small_enough()
            fctval = are_func_vals_close_enough()
            return stddev and fctval
        else:
            if not is_max_length_small_enough():
                return False
            stddev = is_fct_stddev_small_enough()
            fctval = are_func_vals_close_enough()
            return stddev or fctval

        return False

        # TODO: what is this code meant to be doing as it is unreachable?
        num = 2.0 * abs(self.simplex[0, -1] - self.simplex[-1, -1])
        denom = abs(self.simplex[0, -1]) + abs(self.simplex[-1, -1]) + 1.0
        if num / denom > ftol:
            return False

        func_vals = [col[-1] for col in self.simplex]
        if np.std(func_vals) > ftol:
            return False

        return True

    def eval_simplex(self, npop, simplex):
        for ii in range(npop):
            simplex[ii][-1] = self.func(simplex[ii][:-1])
        return self.sort_me(simplex)

    def init(self, npop, xpar, step, seed, factor):
        raise NotImplementedError("init has not been implemented")

    def init_random_simplex(self, xpar, simplex, start, npop, seed, factor):
        # Set the seed when there is no RNG set, otherwise the RNG
        # determines the state.
        #
        if self.rng is None:
            np.random.seed(seed)

        # This could be done before changing the seed, but code may
        # require the current behavior.
        #
        if start >= npop:
            return simplex

        # Note that factor can be None when there's nothing to do
        # here, hence the early-return above.
        #
        deltas = factor * np.abs(np.asarray(xpar))
        for ii in range(start, npop):
            simplex[ii][:-1] = \
                np.array([uniform(self.rng,
                                  max(xmin, xp - delta),
                                  min(xmax, xp + delta))
                          for xmin, xmax, xp, delta in zip(self.xmin,
                                                           self.xmax,
                                                           xpar,
                                                           deltas)])

        return simplex

    def move_vertex(self, centroid, coef):
        vertex = (1.0 + coef) * centroid - coef * self.simplex[self.npar]
        vertex[-1] = self.func(vertex[:-1])
        return vertex

    def shrink(self, shrink_coef):
        npars_plus_1 = self.npar + 1
        for ii in range(1, npars_plus_1):
            self.simplex[ii] = \
                self.simplex[0] + shrink_coef * \
                (self.simplex[ii] - self.simplex[0])
            self.simplex[ii, -1] = self.func(self.simplex[ii, :-1])

    def sort_me(self, simp):
        myshape = simp.shape
        tmp = np.array(sorted(simp, key=lambda arg: arg[-1]))
        tmp.reshape(myshape)
        return tmp

    def sort(self):
        self.simplex = self.sort_me(self.simplex)


class SimplexNoStep(SimplexBase):

    def init(self, npop, xpar, step, seed, factor):
        npar1 = self.npar + 1
        simplex = np.empty((npop, npar1))
        simplex[0][:-1] = np.copy(xpar)
        for ii in range(self.npar):
            tmp = np.copy(xpar)
            if 0.0 == tmp[ii]:
                tmp[ii] = 2.5e-4
            else:
                tmp[ii] *= 1.05
            simplex[ii+1][:-1] = tmp[:]

        simplex = self.init_random_simplex(xpar, simplex, start=npar1,
                                           npop=npop, seed=seed,
                                           factor=factor)
        return self.eval_simplex(npop, simplex)


class SimplexStep(SimplexBase):

    def init(self, npop, xpar, step, seed, factor):
        npar1 = self.npar + 1
        simplex = np.empty((npop, npar1))
        simplex[0][:-1] = np.copy(xpar)
        for ii in range(self.npar):
            tmp = xpar[ii] + step[ii]
            simplex[ii + 1][:-1] = tmp

        simplex = self.init_random_simplex(xpar, simplex, start=npar1,
                                           npop=npop, seed=seed, factor=factor)
        return self.eval_simplex(npop, simplex)


class SimplexRandom(SimplexBase):

    def init(self, npop, xpar, step, seed, factor):
        npar1 = self.npar + 1
        simplex = np.empty((npop, npar1))
        simplex[0][:-1] = np.copy(xpar)

        simplex = self.init_random_simplex(xpar, simplex, start=1,
                                           npop=npop, seed=seed,
                                           factor=factor)
        return self.eval_simplex(npop, simplex)
