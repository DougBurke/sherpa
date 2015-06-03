************
Installation
************

Requirements
============

Sherpa has the following requirements:

  - Python 2.7
  - NumPy

The IPython_ environment - including its notebook support -
is not required but strongly recommended.    
    
Optional features are provided by the following packages
(several can be provided by multiple packages):    

  - matplotlib_: plotting support
  - ChIPS_: plotting support (used by CIAO_).
  - AstroPy_: support for reading and writing FITS_ files
    (this is *coming soon*).
  - PyFITS_: support for reading and writing FITS_ files.
  - crates_: support for reading and writing FITS_ files
    (used by CIAO_).
  - DS9_: for displaying image data.
  - Xspec_: for access to the X-Spec model library (used to
    model Astronomical X-ray data).
  
Installing Sherpa
=================

Anaconda python distribution
----------------------------

The Chandra X-ray Center (CXC_) provides binary packages of
Sherpa and PyFITS_::

  conda config --add channels https://conda.binstar.org/sherpa
  conda install pyfits sherpa

The binary packages are *not* frequently updated, and so may well
lag behind the `Sherpa GitHub repository <https://github.com/sherpa/sherpa>`_.

Testing an installed Sherpa
---------------------------

Sherpa provides a command-line tool for testing the installation::

  sherpa_test

It can also be tested directly, using::

  import sherpa
  sherpa.test()

Any errors should be reported to the
`Sherpa issue tracker <https://github.com/sherpa/sherpa/issues>`_.

Building from source
====================

Sherpa requires:

  - Setuptools
  - gcc, g++, and gfortran
  - make, flex, and bison

There are several libraries that are packaged up with Sherpa,
but can be over-ridden to use a local copy if required, as
described in the `Custom source build`_ section.

Obtaining the source
--------------------

Source packages
^^^^^^^^^^^^^^^

The latest stable source packages is available from *somewhere*.
The build installation for the stable package may be different
to that presented here, as changes have been made to use common
Python techniques.

Development
^^^^^^^^^^^

The development version can be cloned from GitHub using the command::

  git clone https://github.com/sherpa/sherpa

Building and installing
-----------------------

Sherpa uses the setuptools framework for building and installing.
**TODO** is this still correct?

The following commands are run from the root of the source tree;
that is, the location into which the Sherpa code has been placed.
It is strongly advised that a virtual environment - such as
provided by `conda <http://conda.pydata.org/docs/>`_ or
`virtualenv <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_ - is used.

To build Sherpa::

  python setup.py build

To install into a system location::

  python setup.py install

To install into a local location (for instance, if you do not have
write permission to the system location)::

  python setup.py install --user

Custom source build
-------------------

There are several options for customizing the Sherpa build.

FFTW library
^^^^^^^^^^^^

Sherpa ships with the FFTW_ library source
code and builds it as part of its own build process by
default. The ``setup.cfg`` file can be edited to instead
build against a local version of this library. The options
to change are::

  fftw=local
  fftw-include-dirs=/usr/local/include
  fftw-lib-dirs=/usr/local/lib
  fftw-libraries=fftw3

where the values should be adjusted to match the location
of the include file and the library (which defaults to
``libfftw3.so`` but can be changed using the
``fftw-libraries`` option).

X-Spec
^^^^^^

The Xspec_ model library will be built by changing the following
settings in ``setup.cfg``::

  with-xspec=True
  xspec_lib_dirs=/opt/xspec/lib
  cfitsio_lib_dirs=/opt/xspec/lib
  ccfits_lib_dirs=/opt/xspec/lib
  gfortran_lib_firs=/usr/local/lib

where the paths should be adjusted accordingly, for the location
of the X-Spec, CFITSIO, CCfits, and the version of ``gfortran``
used to build X-Spec.

Building documentation
======================

At present the documentation is being built with Sphinx_,
and requires that IPython_ and matplotlib_ be installed. It is in the
*very-early* stages (as you can see), so additional
requirements may be added.

The current documentation can be built with the following command,
run from the root of the source tree::

  python setup.py build_sphinx

To build the documentation for the installed version::

  cd docs
  make html

Testing a source code build of Sherpa
=====================================

Tests can be run from the top-level of the source distribution
with the command::

  python setup.py test

This runs a basic set of tests, referred
to as "smoke" tests, that performs limited validation of
the package. The full test suite requires additional data,
provided by https://github.com/sherpa/sherpa-test-data,
which can be added to the source code directory with the
following commands::

  git submodule init
  git submodule update

After this, the tests suite will run more tests. It is still
run with the command::
  
  python setup.py test

Note that the number of tests that are run depend on what
Python packages and external software are installed, such as
matplotlib_, AstroPy_, and DS9_.

.. include:: links.txt
