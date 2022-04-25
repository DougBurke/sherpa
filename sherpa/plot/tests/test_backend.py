#
#  Copyright (C) 2022
#      MIT
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
import pytest

from sherpa.plot.backends import IndepOnlyBackend


def test_IndepOnlyBackend_raises_for_values():
    '''The IndepOnlyBackend is supposed to raise exceptions when
    called with parameters that are not in the
    backend-independent list.'''
    back = IndepOnlyBackend()
    with pytest.raises(ValueError, match='but got xxx'):
        back.plot(1, 2, linestyle='xxx')

    with pytest.raises(TypeError,
        match='contour got keyword argument color, which is not part of the named keyword arguments'):
        back.contour(1, 2, 3, color='yyy')


def test_IndepOnlyBackend_raises_for_arguments():
    '''The IndepOnlyBackend is supposed to raise exceptions when
    called with keywords that are not in the
    backend-independent list.'''
    back = IndepOnlyBackend()
    with pytest.raises(TypeError,
                       match='plot got keyword argument notthis'):
        back.plot(1, 2, notthis=5)
