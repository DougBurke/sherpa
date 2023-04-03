#
#  Copyright (C) 2007, 2015, 2016, 2018, 2019, 2020, 2023
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

"""Catch all for optimiser tests"""

import numpy as np

import pytest

from sherpa.optmethods.opt import SimplexRandom


def rosenbrock(x):
    """Rosenbrock(1, 1) = 0
    """
    val = np.sum(100.0*(x[1:]-x[:-1]**2.0)**2.0 + (1-x[:-1])**2.0, axis=0)
    return val


SEED = 2354


@pytest.mark.parametrize("rng", [None,
                                 np.random.RandomState(2354)])
def test_is_simplexbase_repeatable(rng):
    """The SimplexBase* classes uses RNG, so can we make it repeatable?

    This is based on the 'if __name__ == "__main__"' section of
    opt.py, (see issue #1737 in case the code gets cleaned up) and
    only one of the classes based on SimplexBase is used.

    The point of the test is to pick a npop size large enough so that
    the Simplex class seeds the simplex with randomly-distributed
    parameter values. For the SimpexRandom case this is npop>1.

    """

    x0 = np.array([-1.2, 1.0])
    xmin = [-1000, -1000]
    xmax = [1000, 1000]
    simp = SimplexRandom(func=rosenbrock, npop=4, xpar=x0, xmin=xmin,
                         xmax=xmax, step=x0 + 1.2, seed=SEED,
                         factor=10, rng=rng)

    # After the first line, which is the x0 array + function value,
    # the next three rows have 2 random numbers and then the function
    # value at that coordinate, and then sorted on the last column.
    # So this tests how repeatable the RNG us.
    #
    expected = np.asarray([[-1.2, 1.0, 24.2],
                           [-3.35073356, 10.0887400, 148.587036],
                           [-4.81446429, -5.89369307, 8.45563422e+04],
                           [6.25720004, 2.32379451, 1.35663379e+05]])
    assert simp.simplex == pytest.approx(expected)


def test_is_simplexbase_repeatable_post_117():
    """test_is_simplese_repeatable with a post NumPy 1.17 RNG.

    It's not clear how "repeatable" this will be (i.e. using
    a fixed seed is not guaranteed to give the same results
    over NumPy versions).

    """

    # The seed argument to SimplexRandom should not be used, so send
    # it a different value to the one used with the RNG.
    #
    rng = np.random.default_rng(SEED)

    x0 = np.array([-1.2, 1.0])
    xmin = [-1000, -1000]
    xmax = [1000, 1000]
    simp = SimplexRandom(func=rosenbrock, npop=4, xpar=x0, xmin=xmin,
                         xmax=xmax, step=x0 + 1.2, seed=SEED + 1,
                         factor=10, rng=rng)

    expected = np.asarray([[-1.2, 1.0, 24.2],
                           [-1.56818621, -3.88919619, 4.03681915e+03],
                           [ 4.48924317, -0.37612188, 4.21579083e+04],
                           [-8.84949593,  9.70166152, 4.70856524e+05]])
    assert simp.simplex == pytest.approx(expected)
