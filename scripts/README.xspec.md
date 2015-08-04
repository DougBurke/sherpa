
# Notes on building the Xspec model

The Xspec library contains a file called model.dat that defines the
models it contains, and the parameters for these models (there's
another file, called mixmodel.dat, but Sherpa does not currently
support the models in this file). There are two files which use the
information from model.dat:

1) sherpa/astro/xspec/__init__.py

The class definitions that define the Sherpa model interface to
these models. For example, the folloqing defines the "xsapec"
model, which calls the Xspec apec model, and has four parameters:
kT, Abundanc, redshift, and norm:

class XSapec(XSAdditiveModel):

    _calc =  _xspec.xsaped

    def __init__(self, name='apec'):
        self.kT = Parameter(name, 'kT', 1., 0.008, 64.0, 0.0, hugeval, 'keV')
        self.Abundanc = Parameter(name, 'Abundanc', 1., 0., 5., 0.0, hugeval, frozen=True)
        self.redshift = Parameter(name, 'redshift', 0., -0.999, 10., -0.999, hugeval, frozen=True)
        self.norm = Parameter(name, 'norm', 1.0, 0.0, 1.0e24, 0.0, hugeval)
        XSAdditiveModel.__init__(self, name, (self.kT, self.Abundanc, self.redshift, self.norm))

2) sherpa/astro/xspec/src/_xspec.cc

There are two places:

i) in the extern "C" block, where the functions are declared: for example

void xsaped_(float* ear, int* ne, float* param, int* ifl, float* photar, float* photer);
void C_xscflw(const double* energy, int nFlux, const double* params, int spectrumNumber, double* flux, double* fluxError, const char* initStr);

Note that there are several different interfaces that are possible, but
we generally only see the two listed above.

ii) in the XspecMethods list

This is used to create the Python-callable function which calls the
Xspec model library function. It relies on the templates in
sherpa/include/sherpa/astro/xspec_extension.hh, and looks something
like

  XSPECMODELFCT_NORM( xsaped, 4 ),
  XSPECMODELFCT_C_NORM( C_xsbexrav, 10 ),
  XSPECMODELFCT_C( C_xsabsori, 6 ),
  XSPECMODELFCT( acisabs, 8 ),

# What about other parts of the interface?

There are other parts, in particular _xspec.cc contains code to interface
to utility functions in the API (e.g. returning the library version, or
changing the abundance tables). This interface is harder to automate,
as you have to rely on include files (primarily xsFortran.h or
FunctionUtility.h) to determine what is and isn't available. For that
reason I only focus on the contents of model.dat.

# How was the interface originally created?

The interface appears to have been created by scripts/create_xspec_extension,
which was used to create the file xspec.out. This was then inserted into
the relavant parts of the code base, and manually changed when new versions
of Xspec were released. This makes it hard to track down how well what was
changed (and has lead to new models not being added when they could, or
parameter changes not being tracked).

I have created an updated version of the script - based on code I have
used to provide interfaces to Xspec user models from Sherpa in CIAO - as
an experiment. The output of this script is not yet included in the build,
since it's not clear to me how to integrate this in the build, and I first
want to check that the code output matches (to expected changes) the
existing code, when run against XSpec 12.8.2e (the current version of the
Xspec model interface supported by Sherpa).

# Running the new code

The new code is written as a module in scripts/xspec/modelparse.py, and
for testing purposes can be run as a script:

% python xspec/modelparse.py /path/to/model.dat test
INFO:__main__:Skipping model smaug as it needs to be re-evaluated per spectrum.
INFO:__main__:Skipping pileup as model type = Acn
Created: test.py/declare/methoddef.incl

Which creates three files

- test.py.incl
- test.declare.incl
- test.methoddef.incl

corresponding to the three sections discussed above.
