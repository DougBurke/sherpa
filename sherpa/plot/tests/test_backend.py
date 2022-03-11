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

from sherpa.plot.backends import IndepOnlyBackend, get_keyword_defaults, translate_args
from sherpa.utils.testing import requires_pylab


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


class ExampleClass():
    def __init__(self, translate_dict={}):
        self.translate_dict = translate_dict

    @translate_args
    def func(self, a, b, c='qwer'):
        return a, b, c


def test_translate_dict():
    """Test that a translatedict filled with dicts works"""
    t = ExampleClass({'a': {'val1': 'val2'},
                      'c': {None: 5, 5: 6}})
    # No translation of value not in dict
    assert (3, 4, 2.) == t.func(3, 4, c=2.)
    # translate value for just one of the values 
    assert ('val1', 4, 2.) == t.func('val1', 4, 2.)
    # translate all
    assert ('val2', 7, 6) == t.func(a='val1', b=7, c=5)
    # translate does only translate keyword arguments
    assert ('val1', 7, 6) == t.func('val1', 7, c=5)


def test_translate_func():
    """Test that a translatedict filled with functions works"""
    t = ExampleClass({'a': {'val1': 'val2'},
                      'c': lambda x: x * 2})
    assert ('a', 'b', 16) == t.func('a', 'b', c=8)


def test_keyword_defaults():
    """Check that we get a dictonary of the default values defined in a function"""
    def func(a, b=5, c=None):
        pass
    assert get_keyword_defaults(func) == {'b': 5, 'c': None}


def test_keyword_defaults_method():
    """Repeat the test above for a method"""
    class MyClass():
        def func(self, a, b=5, c=None):
            pass

        def keyword(self):
            return get_keyword_defaults(self.func)

    assert get_keyword_defaults(MyClass.func) == {'b': 5, 'c': None}
    myinstance = MyClass()
    assert MyClass.keyword(MyClass) == {'b': 5, 'c': None}
