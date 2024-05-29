#
#  Copyright (C) 2024
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

"""Useful types for Sherpa.

This module should be considered an internal module as its contents is
likely to change as types get added to Sherpa and the typing ecosystem
in Python matures.

"""

from typing import Any, Callable, Protocol, Sequence, Union

import numpy as np


# Some of these may change to TypeAlias (once Python 3.10 is the
# minimum) and then type/TypeAliasType once Python 3.12 is the
# minimum.
#

# Try to be generic when using arrays as input or output. There is no
# attempt to encode the data type or shape for ndarrays at this time.
#
ArrayType = Union[Sequence[float], np.ndarray]

# Represent statistic evaluation.
#
StatErrFunc = Callable[..., ArrayType]
StatResults = tuple[float, np.ndarray]
StatFunc = Callable[..., StatResults]

# Represent model evaluation. Using a Protocol may be better, but
# for now keep with a Callable. Ideally the model would just
# return an ndarray but
#
# - an ArithmeticConstantModel can return a scalar
# - models could return a sequence rather than a ndarray
#
ModelFunc = Callable[..., ArrayType]

# The return value of an optimization routine. It would be better
# to have this typed, but leave as is for now.
#
OptResults = tuple[bool,           # success flag
                   np.ndarray,     # best-fit parameter values
                   float,          # statistic vaule
                   str,            # status message
                   dict[str, Any]  # return extra information
                   ]

# Use a Protocol rather than a Callable since each optimizer
# can have their own keyword values.
#
class OptFunc(Protocol):
    """Represent the optimization function.

    This only lists the required arguments. The optimization-specific
    keyword arguments are not included here.

    """

    def __call__(self,
                 fcn: StatFunc,
                 x0: ArrayType,
                 xmin: ArrayType,
                 xmax: ArrayType
                 ) -> OptResults:
        ...
