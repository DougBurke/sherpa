#
#  Copyright (C) 2007, 2015  Smithsonian Astrophysical Observatory
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

import unittest
import numpy
from sherpa.astro import ui
from sherpa.utils import SherpaTestCase, test_data_missing
from sherpa.utils import has_package_from_list, has_fits_support

import logging
error = logging.getLogger(__name__).error

def is_proper_subclass(obj, cls):
    if type(cls) is not tuple:
        cls = (cls,)
    if obj in cls:
        return False
    return issubclass(obj, cls)


@unittest.skipIf(not has_package_from_list('sherpa.astro.xspec'),
                 "required sherpa.astro.xspec module missing")
class test_xspec(SherpaTestCase):

    def test_create_model_instances(self):
        import sherpa.astro.xspec as xs
        count = 0

        for cls in dir(xs):
            if not cls.startswith('XS'):
                continue

            cls = getattr(xs, cls)

            if is_proper_subclass(cls, (xs.XSAdditiveModel,
                                        xs.XSMultiplicativeModel,
                                        xs.XSConvolutionKernel)):
                m = cls()
                count += 1

        self.assertEqual(count, 178)

    def test_evaluate_model(self):
        import sherpa.astro.xspec as xs
        m = xs.XSbbody()
        out = m([1,2,3,4])
        if m.calc.__name__.startswith('C_'):
            otype = numpy.float64
        else:
            otype = numpy.float32
        self.assert_(out.dtype.type is otype)
        self.assertEqual(int(numpy.flatnonzero(out == 0.0)), 3)


    def test_xspec_models(self):
        import sherpa.astro.xspec as xs
        models = [model for model in xs.__all__ if model[:2] == 'XS' and
                  not is_proper_subclass(getattr(xs, model),
                                         xs.XSConvolutionKernel)]
        models.remove('XSModel')
        models.remove('XSMultiplicativeModel')
        models.remove('XSAdditiveModel')
        models.remove('XSTableModel')
        models.remove('XSConvolutionModel')
        models.remove('XSConvolutionKernel')

        xx = numpy.arange(0.1, 11.01, 0.01, dtype=float)
        xlo = numpy.array(xx[:-1])
        xhi = numpy.array(xx[1:])
        for model in models:
            cls = getattr(xs, model)
            foo = cls('foo')
            vals = foo(xlo,xhi)
            try:
                self.assert_(not numpy.isnan(vals).any() and
                             not numpy.isinf(vals).any() )
            except AssertionError:
                error('XS%s model evaluation failed' % model)
                raise

    @unittest.skipIf(not has_fits_support(),
                     'need pycrates, pyfits')
    @unittest.skipIf(test_data_missing(), "required test data missing")
    def test_set_analysis_wave_fabrizio(self):
        rmf = self.datadir + '/ciao4.3/fabrizio/Data/3c273.rmf'
        arf = self.datadir + '/ciao4.3/fabrizio/Data/3c273.arf'

        ui.set_model("fabrizio", "xspowerlaw.p1")
        ui.fake_pha("fabrizio", arf, rmf, 10000)

        model = ui.get_model("fabrizio")
        bare_model, _ = ui._session._get_model_status("fabrizio")
        y = bare_model.calc([1,1], model.xlo, model.xhi)
        y_m = numpy.mean(y)

        ui.set_analysis("fabrizio","wave")

        model2 = ui.get_model("fabrizio")
        bare_model2, _ = ui._session._get_model_status("fabrizio")
        y2 = bare_model2.calc([1,1], model2.xlo, model2.xhi)
        y2_m = numpy.mean(y2)

        self.assertAlmostEqual(y_m, y2_m)

    def test_xsxset_get(self):
        import sherpa.astro.xspec as xs
        # TEST CASE #1 Case insentitive keys
        xs.set_xsxset('fooBar', 'somevalue')
        self.assertEqual('somevalue', xs.get_xsxset('Foobar'))

    # Copied from my xspec-contiguous branch and updated to use the Python
    # interface rather than the low-level API.
    def test_convolution_models(self):
        # Use the cflux convolution model since this gives
        # an "easily checked" result.
        import sherpa.astro.xspec as xs

        # Want the energy grid to extend beyond the energy grid
        # used to evaluate the model, to avoid any edge effects.
        # It also makes things easier if the elo/ehi values align
        # with the egrid bins.
        elo = 0.55
        ehi = 1.45
        egrid = numpy.linspace(0.5, 1.5, 101)

        mdl1 = xs.XSpowerlaw()
        mdl1.PhoIndex = 2

        # flux of mdl1 over the energy range of interest; converting
        # from a flux in photon/cm^2/s to erg/cm^2/s, when the
        # energy grid is in keV.
        y1 = mdl1(egrid)
        idx, = numpy.where((egrid >= elo) & (egrid < ehi))

        # To match XSpec, need to multiply by (Ehi^2-Elo^2)/(Ehi-Elo)
        # which means that we need the next bin to get Ehi. Due to
        # the form of the where statement, we should be missing the
        # Ehi value of the last bin
        e1 = egrid[idx]
        e2 = egrid[idx+1]

        f1 = 8.01096e-10 * ((e2*e2-e1*e1) * y1[idx] / (e2-e1)).sum()

        # The cflux parameters are elo, ehi, and the log of the
        # flux within this range (this is log base 10 of the
        # flux in erg/cm^2/s). The parameters chosen for the
        # powerlaw, and energy range, should have f1 ~ 1.5e-9
        # (log 10 of this is -8.8).
        lflux = -5.0
        xs.load_xscflux("cmdl")

        mid = 'test-conv'
        ui.load_arrays(mid, egrid, egrid*0) # defaults to Data1D
        ui.set_source(mid, cmdl(mdl1))

        cmdl.emin = elo
        cmdl.emax = ehi
        cmdl.lg10flux = lflux

        # What's the best way to evaluate the source model on
        # the grid?
        ##y2 = ui.get_data(mid).eval_model(cmdl(mdl1))
        y2 = ui.get_model_plot(mid).y

        expected = y1 * 10**lflux / f1
        numpy.testing.assert_allclose(expected, y2)

        # TODO: should test elo/ehi and wavelength
        ui.clean()

if __name__ == '__main__':
    import sherpa.astro.xspec as xs
    from sherpa.utils import SherpaTest
    SherpaTest(xs).test()
