#
#  Copyright (C) 2010, 2016, 2018, 2019, 2020, 2021, 2022, 2023
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

import numpy as np

import pytest

from sherpa.utils import SherpaFloat
from sherpa.utils.random import poisson_noise


def test_poisson_noise():
    out = poisson_noise(1000)
    assert type(out) == SherpaFloat
    assert out > 0.0

    for x in (-1000, 0):
        out = poisson_noise(x)
        assert type(out) == SherpaFloat
        assert out == 0.0

    out = poisson_noise([1001, 1002, 0.0, 1003, -1004])
    assert type(out) == np.ndarray
    assert out.dtype.type == SherpaFloat

    ans = np.flatnonzero(out > 0.0)
    assert (ans == np.array([0, 1, 3])).all()

    with pytest.raises(ValueError):
        poisson_noise('ham')

    with pytest.raises(TypeError):
        poisson_noise(1, 2, 'ham')
