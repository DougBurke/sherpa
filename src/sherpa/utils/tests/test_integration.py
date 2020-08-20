#
#  Copyright (C) 2007, 2016, 2018, 2019, 2020  Smithsonian Astrophysical Observatory
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
import sherpa.utils.integration as integration
from sherpa.testing import SherpaTestCase


class test_integration(SherpaTestCase):
    "py3-todo: is integration.so even ever used?"
    def test_c_api(self):
        self.assertTrue(hasattr(integration, '_C_API'))
        self.assertEqual(type(integration._C_API).__name__, 'PyCapsule')
