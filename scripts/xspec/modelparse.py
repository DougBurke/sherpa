#
#  Copyright (C) 2012, 2013, 2014, 2015
#    Smithsonian Astrophysical Observatory
#
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
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

"""Create an interface to the Xspec model library.

This module provides routines to parse the model.dat file - which
is used by Xspec to define available models - and create code
fragments needed by the Sherpa interface to this library.

It is *highly experimental*.
"""

# OLD TODO ITEMS: STILL RELEVANT?
#   can models that need to be re-evaluated per spectrum (mfl.flags[1]==1)
#   be supported purely by turning off the cache code, or is it
#   possible that thet need access to X-Spec internals? Actually, the
#   following suggests that it can just be ignored (but then how
#   about with flags[0] == 1 or any with an initString). ==>
#   NOTE: should be careful with these as they likely need XFLT/whatever,
#   so skip for now
#
#   It looks like initpackage does not use the flags for each model - that
#   is the two integers after the model type. The initialization code it
#   creates passes the model definition file to
#   XSModelFunction::updateComponentList(), which I guess does care about
#   these. This function is in
#   heasoft-6.16/Xspec/src/XSUtil/FunctionUtils/XSModelFunction.cxx
#
#   some following of bread crumbs leads to the fact that can have
#     ... fnname mdltype 0/1 0/1
#     ... fnname mdltype 0/1 string
#     ... fnname mdltype 0/1 0/1 string
#
#   where the first boolean is referred to m_error and the second is
#   m_isSpectrumDependency, with the string being m_initString
#   (from XSModel/Model/Component/Component.cxx). The
#   isSpectrumDependency and isError methods access the bool values
#   and initString the string.
#
#   Looks like isSpectrumDependency is only used by XSModel/Model/ModelBase.cxx
#   in setting up the checkForSpecDependency routine to set the
#   m_areCompsSpecDependent flag / areCompsSpecDependent accessor.
#
#   From tracking through the code, it looks like the specturm dependency
#   flag is used in UniqueEnergyManager::addRespEnergy() to determine
#   whether a new energy grid is needed. From my understanding of the
#   Sherpa internals, this is not relevant, ie we can ignore this
#   particular flag.
#


import string
import logging

logger = logging.getLogger(__name__)
debug = logger.debug
info = logger.info
warn = logger.warn

valid_chars = string.ascii_letters + string.digits + '_'


def validate_namefunc(namefunc):
    """Raise a ValueError if namefunc does not capitalize the return string."""
    inval = 'bob'
    outval = namefunc(inval)
    if not outval[0].isupper():
        raise ValueError("The namefunc routine does not capitalize the return value - e.g. '{}' -> '{}'.".format(inval, outval))


def convert_parname(modelname, parname):
    """Return an acceptable python name for the parameter.

    Parameters
    ----------
    modelname: str
       The name of the model.
    parname: str
       The name of the parameter

    Returns
    -------
    name: str
       The name of the parameter for use by Sherpa.

    Notes
    -----
    Xspec parameter names do not necessarily match Python rules for a
    field name. There does not appear to have been a single scheme used
    for translating parameter names, so this function contains (or
    will contain) a bunch of hard-coded rules based on the model name.
    """

    if parname.startswith('<') and parname.endswith('>'):
        name = parname[1:-1] + "_ave"
    else:
        name = parname

    name = name.replace('@', 'At')

    # replace foo(bar) with foo_bar
    # (do this before the following, otherwise have foo_bar_)
    #
    if name.endswith(')'):
        lpos = name.rfind('(')
        if lpos != -1:
            name = name[:lpos] + "_" + name[lpos + 1:-1]

    # Remove unsupported characters
    # name = "".join([t for t in name if t in valid_chars])

    # Replace unsupported characters with '_'. I'd like
    # to use .translate(), but I am too lazy to see how
    # this works.
    def cconv(c):
        if c in valid_chars:
            return c
        else:
            return '_'

    name = "".join(map(cconv, name))

    if name in ["break", "lambda", "type"]:
        name += "_"

    return name


def add_prefix(prefix, inval):
    """Returns prefix prepended to inval (converting it to a string if
    necessary)."""
    return "{}{}".format(prefix, inval)


def add_xs_prefix(inval):
    """Returns XS prepended to inval (converting it to a string if
    necessary)."""
    return add_prefix("XS", inval)


def no_prefix(inval):
    """Returns inval converted to a string, after converting
    the first character to upper case.
    """
    return str(inval).capitalize()


class ModelLanguage:
    """What is the language interface for a model."""

    FORTRAN_STYLE = 1
    FORTRANDP_STYLE = 2
    C_STYLE = 3
    CPP_STYLE = 4

    labels = {1: 'Fortran - single precision',
              2: 'Fortran - double precision',
              3: 'C',
              4: 'C++'}


class ModelDefinition():
    """Represent the model definition from an X-Spec model file.

    Do not instantiate this class directly.

    The clname attribute gives the class name used to represent
    this model - so must start with a capital letter - and is
    also used (in lower-case form) as the model name that users
    enter when creating an instance.

    The language field determines the interface type - e.g.
    Fortran, C, or C++. It is possible to have C code labelled
    as using the Fortran interface.
    """

    modeltype = None
    language = None

    def __init__(self, name, clname, funcname, flags, elo, ehi, pars):
        elbl = "ModelDefinition should not be directly created."
        assert self.modeltype is not None, elbl

        self.name = name
        self.clname = clname
        self.flags = flags
        self.elo = elo
        self.ehi = ehi
        self.pars = pars

        # This will probably need to be changed if mixing models
        # (mix or amx) are supported.
        #
        # Originally I removed the "language tag" but for now leave
        # back in.
        #
        # Is it upper or lowercase f?
        if funcname.startswith('F_'):
            self.language = ModelLanguage.FORTRANDP_STYLE
            # self.funcname = funcname[2:]
            self.funcname = funcname
        elif funcname.startswith('c_'):
            self.language = ModelLanguage.C_STYLE
            # self.funcname = funcname[2:]
            self.funcname = funcname
        elif funcname.startswith('C_'):
            self.language = ModelLanguage.CPP_STYLE
            # self.funcname = funcname[2:]
            self.funcname = funcname
        else:
            self.language = ModelLanguage.FORTRAN_STYLE
            self.funcname = funcname

    def __str__(self):
        pars = "\n".join([str(p) for p in self.pars])
        lang = ModelLanguage.labels[self.language]
        return "{}.{} function={}\n{}\n{}".format(self.modeltype,
                                                  self.name,
                                                  self.funcname,
                                                  lang,
                                                  pars)

    def make_wrapper(self):
        """Return the code needed to create a Python wrapper to the
        model function.
        """
        raise NotImplementedError("This must be over-ridden")


class AddModelDefinition(ModelDefinition):
    """X-Spec additive models. See
    http://heasarc.gsfc.nasa.gov/docs/software/lheasoft/xanadu/xspec/manual/Additive.html
    for examples."""
    modeltype = "Add"

    def make_wrapper(self):
        funcname = self.funcname
        if self.language in [ModelLanguage.FORTRAN_STYLE,
                             ModelLanguage.FORTRANDP_STYLE]:
            template = ""
        else:
            template = "_C"

        return "XSPECMODELFCT{}_NORM( {}, {} )".format(template,
                                                       funcname,
                                                       len(self.pars))


class MulModelDefinition(ModelDefinition):
    """X-Spec multiplicative models. See
    http://heasarc.gsfc.nasa.gov/docs/software/lheasoft/xanadu/xspec/manual/Multiplicative.html
    for examples."""
    modeltype = "Mul"

    def make_wrapper(self):
        funcname = self.funcname
        if self.language in [ModelLanguage.FORTRAN_STYLE,
                             ModelLanguage.FORTRANDP_STYLE]:
            template = ""
        else:
            template = "_C"

        return "XSPECMODELFCT{}( {}, {} )".format(template,
                                                  funcname,
                                                  len(self.pars))


class ConModelDefinition(ModelDefinition):
    """X-Spec convolution models. See
    http://heasarc.gsfc.nasa.gov/docs/software/lheasoft/xanadu/xspec/manual/Convolution.html
    for examples."""
    modeltype = "Con"

    def make_wrapper(self):
        return "XSPECMODELFCT_C( {}, {} )".format(self.funcname,
                                                  len(self.pars))


class MixModelDefinition(ModelDefinition):
    """X-Spec mixing models. See
    http://heasarc.gsfc.nasa.gov/docs/software/lheasoft/xanadu/xspec/manual/Mixing.html
    for examples."""
    modeltype = "Mix"


class AcnModelDefinition(ModelDefinition):
    """X-Spec Acn models: pile up models"""
    modeltype = "Acn"


# Found in looking through
# heasoft-6.16/Xspec/src/tools/initpackage/ModelMap.cxx
class AmxModelDefinition(ModelDefinition):
    """X-Spec Amx models: """
    modeltype = "Amx: apparently a combination of mixing and pile-up models"


class ParameterDefinition():
    """Base class for parameters. These classes take a
    parameter - as defined for an Xspec model - and convert
    it into the code needed to implement this in a Sherpa model.
    """

    paramtype = None

    def __init__(self, name, default, units=None,
                 softmin=None, softmax=None,
                 hardmin=None, hardmax=None, delta=None):
        elbl = 'ParameterDefinition should not be directly created'
        assert self.paramtype is not None, elbl

        self.name = name
        self.default = default
        self.units = units

        self.softmin = softmin
        self.softmax = softmax
        self.hardmin = hardmin
        self.hardmax = hardmax
        if delta is None:
            self.delta = None
        else:
            self.delta = abs(delta)

    def param_string(self):
        elbl = "param_string has not been overridden for name={} paramtype={}".format(self.name, self.paramtype)
        raise NotImplementedError(elbl)


class SwitchParameterDefinition(ParameterDefinition):

    paramtype = "Switch"

    def __str__(self):
        return "{} = {}".format(self.name, self.default)

    def param_string(self):
        out = "Parameter(name, '{}', {}".format(self.name, self.default)

        for (pval, pname) in [(self.softmin, "min"),
                              (self.softmax, "max"),
                              (self.hardmin, "hard_min"),
                              (self.hardmax, "hard_max")]:
            if pval is not None:
                out += ",{}={}".format(pname, pval)

        if self.units is not None:
            out += ",units='{}'".format(self.units)

        out += ",alwaysfrozen=True)"
        return out


class ScaleParameterDefinition(ParameterDefinition):
    """I am not convinced that this code handles scale parameters
    correctly.
    """

    paramtype = "Scale"

    def __str__(self):
        out = "{} = {}".format(self.name, self.default)
        if self.units is not None:
            out += " units={}".format(self.units)
        return out

    def param_string(self):
        out = "Parameter(name, '{}', {}".format(self.name, self.default)

        for (pval, pname) in [(self.softmin, "min"),
                              (self.softmax, "max"),
                              (self.hardmin, "hard_min"),
                              (self.hardmax, "hard_max")]:
            if pval is not None:
                out += ",{}={}".format(pname, pval)

        if self.units is not None:
            out += ",units='{}'".format(self.units)

        out += ",alwaysfrozen=True)"
        return out


class BasicParameterDefinition(ParameterDefinition):

    modeltype = "Basic"

    def __init__(self, name, default, units, softmin, softmax,
                 hardmin, hardmax, delta):

        self.name = name

        self.units = units
        self.softmin = softmin
        self.softmax = softmax

        if self.softmin < 0.0:
            self.hardmin = "-hugeval"
        else:
            self.hardmin = "0.0"

        self.hardmax = "hugeval"

        if default < self.softmin:
            self.default = softmin
        elif default > self.softmax:
            self.default = softmax
        else:
            self.default = default

        if delta < 0.0:
            self.frozen = True
            self.delta = abs(delta)
        else:
            self.frozen = False
            self.delta = delta

    def __str__(self):
        args = self.name, self.default, self.softmin, self.softmax
        out = "{} = {} ({} to {})".format(*args)
        if self.units is not None:
            out += " units={}".format(self.units)
        if self.frozen:
            out += " frozen"
        return out

    def param_string(self):
        args = self.name, self.default, self.softmin, self.softmax, \
               self.hardmin, self.hardmax
        out = "Parameter(name, '{}', {}, min={}, max={}, hard_min={}, hard_max={}".format(*args)
        if self.frozen:
            out += ", frozen=True"
        if self.units is not None:
            out += ", units='{}'".format(self.units)
        out += ")"
        return out


# The normalization parameter used for additive models, since Sherpa
# adds one in to the model itself whereas Xspec handles it differently.
NORM_PARAM_DEF = 'norm " " 1.0 0.0 0.0 1.0e24 1.0e24 0.1'


def read_model_definition(fh, namefunc=add_xs_prefix,
                          nametranslate=convert_parname):
    """Represent the model definition from an Xspec model file.

    A single model definition is read in and returned to the
    user, or None if the end of file has been reached.

    Parameters
    ----------
    fh
       A file handle-like object for reading from.
    namefunc: optional
       The namefunc routine takes the model name (taken from the
       Xspec file) and returns the Python class name for the
       model; at the least it should ensure the first character
       is capitalized. The default is to prepend with XS, which
       means that a user would create an instance of the model
       foobar with xsfoobar.mdl, and the class would be called
       XSfoobar.
    nametranslate: optional
       Used to convert from the Xspec name to a name that can be used
       in Sherpa (i.e. matches Python naming rules).

    Returns
    -------
    model: a sub-class of ModelDefinition
       A representation of the next model in the input stream.

    Notes
    -----
    The format supported here is defined in
    http://heasarc.gsfc.nasa.gov/xanadu/xspec/manual/XSappendixLocal.html

    If an error occurs during parsing then the location of the
    file handle is left at the point of the error - i.e. it
    does not try to continue reading in the rest of this model
    definition.

    """

    hdrline = ''
    while hdrline == '':
        hdrline = fh.readline()
        if hdrline == '':
            return None

        hdrline = hdrline.strip()

    debug("processing hdr line '{}'".format(hdrline))
    toks = hdrline.split()
    ntoks = len(toks)
    if ntoks < 7 or ntoks > 8:
        raise ValueError("Expected: modelname npars elo ehi funcname modeltype i1 [i2] but sent:\n{}".format(hdrline))

    name = toks[0]
    clname = namefunc(name)
    npars = int(toks[1])
    if npars < 0:
        raise ValueError("Number of parameters is {}:\n{}".format(npars, hdrline))

    elo = float(toks[2])
    ehi = float(toks[3])
    funcname = toks[4]
    modeltype = toks[5]
    flags = map(int, toks[6:])
    debug("-> function={} {} npars={} elo={} ehi={} flags={}".format(funcname,
                                                                     modeltype,
                                                                     npars,
                                                                     elo,
                                                                     ehi,
                                                                     flags))

    pars = []
    while len(pars) < npars:
        pline = fh.readline().strip()
        # not sure if it's technically valid to have a blank line here
        # but allow it for now
        if pline == '': continue

        debug(" parameter #{}/{}: {}".format(len(pars) + 1, npars, pline))

        pars.append(process_parameter_definition(pline, name,
                                                 nametranslate=nametranslate))

    if modeltype == "add":
        normpar = process_parameter_definition(NORM_PARAM_DEF, name,
                                               nametranslate=nametranslate)
        pars.append(normpar)
        factory = AddModelDefinition

    elif modeltype == "mul":
        factory = MulModelDefinition

    elif modeltype == "con":
        factory = ConModelDefinition

    elif modeltype == "mix":
        factory = MixModelDefinition

    elif modeltype == "acn":
        factory = AcnModelDefinition

    elif modeltype == "amx":
        factory = AmxModelDefinition

    else:
        raise ValueError("Unexpected model type {} in:\n{}".format(modeltype, hdrline))

    # safety check on the parameter names.
    #
    pnames = [(par.name.lower(), par.name) for par in pars]
    lnames = set(pnames)
    if len(lnames) != len(pars):
        from collections import defaultdict
        d = defaultdict(list)
        for k, v in pnames:
            d[k].append(v)

        multiple = [vs for k, vs in d.items() if len(vs) > 1]
        mstr = [" and ".join(v) for v in multiple]
        raise ValueError("The parameters in model={} do not have unique names:\n  {}".format(name,
                                                                                             "\n  ".join(mstr)))

    return factory(name, clname, funcname, flags, elo, ehi, pars)


def mpop(array, defval=None):
    """Pop first element from array (converting to float),
    returning defval if empty."""

    try:
        return float(array.pop(0))
    except IndexError:
        return defval


def process_parameter_definition(pline, model,
                                 nametranslate=convert_parname):
    """Convert a parameter description to an object.

    Parameters
    ----------
    pline: str
       The parameter description as stored in the Xspec model.dat file.
    model: str, optional
       The name of the model which has the parameter. This is
       used for the name translation and error messages.
    nametranslate: optional
       Used to convert from the Xspec name to a name that can be used
       in Sherpa (i.e. matches Python naming rules).

    Returns
    -------
    par: a subclass of ParamewterDefinition
       The parameter object.
    """

    if pline.endswith("P"):
        raise ValueError("Periodic parameters are unsupported; model={}:\n{}\n".format(model, pline))

    toks = pline.split()
    orig_parname = toks.pop(0)

    name = nametranslate(model, orig_parname)
    if orig_parname != name:
        debug("Converted {0}.{1} -> {0}.{2}".format(model, orig_parname, name))

    if orig_parname.startswith('$'):
        # switch parameter
        # the X-Spec documentation say that switches only have 2 arguments
        # but the model.dat from it's own model definitions includes
        #    $switch    1     0       0     1      1       -1
        #    $method   " "   1       1       1       3       3       -0.01
        #    $model    " "     0
        #
        ntoks = len(toks)
        if ntoks == 1:
            default = int(toks[0])
            return SwitchParameterDefinition(name, default)

        elif ntoks == 6:
            default = int(toks.pop(0))
            hardmin = float(toks.pop(0))
            softmin = float(toks.pop(0))
            softmax = float(toks.pop(0))
            hardmax = float(toks.pop(0))
            delta   = float(toks.pop(0))
            return SwitchParameterDefinition(name, default, None,
                                             softmin, softmax,
                                             hardmin, hardmax, delta)

        elif ntoks > 6:
            # ignore units for now
            delta   = float(toks.pop())
            hardmax = float(toks.pop())
            softmax = float(toks.pop())
            softmin = float(toks.pop())
            hardmin = float(toks.pop())
            default = int(toks.pop())
            return SwitchParameterDefinition(name, default, None,
                                             softmin, softmax,
                                             hardmin, hardmax, delta)

        elif toks[0].startswith('"'):
            # assume something like '$model " " val'
            debug("Switch parameter with pline = {}".format(pline))
            default = int(toks.pop())
            return SwitchParameterDefinition(name, default)

        else:
            emsg = "(switch) model={} pline=\n{}".format(model, pline)
            raise NotImplementedError(emsg)

    # Handle units
    val = toks.pop(0)
    if val.startswith('"'):
        units = val[1:]
        if units.endswith('"'):
            units = units[:-1]

        else:
            flag = True
            while flag:
                try:
                    val = toks.pop(0)
                except IndexError:
                    emsg = "Unable to parse units; model={}\n{}".format(model, pline)
                    raise ValueError(emsg)

                if val.endswith('"'):
                    val = val[:-1]
                flag = False

                units += val

    else:
        units = val

    if units.strip() == '':
        units = None

    if orig_parname.startswith('*'):
        # scale parameter
        default = float(toks.pop(0))

        # if len(toks) > 0:
        #    print("DBG: scale parameter: {}".format(pline))

        hardmin = mpop(toks)
        softmin = mpop(toks)
        softmax = mpop(toks)
        hardmax = mpop(toks)
        delta   = mpop(toks)

        return ScaleParameterDefinition(name, default, units,
                                        softmin, softmax,
                                        hardmin, hardmax, delta)

    if len(toks) != 6:
        debug("len(toks) = {}".format(len(toks)))
        debug("toks = {}".format(toks))
        raise ValueError("Expected 6 values after units; model={}\n{}".format(model, pline))

    default = float(toks.pop(0))
    hardmin = float(toks.pop(0))
    softmin = float(toks.pop(0))
    softmax = float(toks.pop(0))
    hardmax = float(toks.pop(0))
    delta = float(toks.pop(0))

    return BasicParameterDefinition(name, default, units,
                                    softmin, softmax,
                                    hardmin, hardmax, delta)


def parse_model_file(modelfile,
                     namefunc=add_xs_prefix,
                     nametranslate=convert_parname):
    """Given an Xspec model file - e.g. the lmodel.dat file -
    return information about the models it contains.

    Parameters
    ----------
    modelfile: str
       The name of the file to process.
    namefunc: optional
       The namefunc routine takes the model name (taken from the
       Xspec file) and returns the Python class name for the
       model; at the least it should ensure the first character
       is capitalized. The default is to prepend with XS, which
       means that a user would create an instance of the model
       foobar with xsfoobar.mdl, and the class would be called
       XSfoobar.
    nametranslate: optional
       Used to convert from the Xspec name to a name that can be used
       in Sherpa (i.e. matches Python naming rules).

    Returns
    -------
    models: a list of ModelDefinition instances
       A representation of the models in the file. It can be an empty
       list. It should be passed through verify_models to remove
       problematic models.

    Notes
    -----
    The code does not try to recover from an error parsing the file.
    This should probably be addressed, but it is unclear how best to
    recover from an error (i.e. how to skip to the next model).
    """

    out = []
    with open(modelfile, "r") as fh:

        while True:
            # If there is a problem reading in a model definition then
            # we do not try to recover - e.g. by wrapping this in a
            # try/except block - since it is not clear how to skip over
            # the "invalid" model definiton so that we can move to the
            # next model (well, some simple heuristics could be applied,
            # but leave off developing these until it turns out to be
            # a problem).
            #
            # A simple option would be to just stop parsing as soon as
            # there is a problem, but process any parsed model.
            #
            mdl = read_model_definition(fh, namefunc=namefunc)

            if mdl is None:
                break
            else:
                debug("Read in model definition: {}".format(mdl.name))
                out.append(mdl)

    return out


def verify_models(mdls, allow_per_spectrum_models=False):
    """Remove any problematic models.

    Parameters
    ----------
    mdls: output of parse_model_file
    allow_per_spectrum_models: bool, optional
       Set to `True` to allow models which are marked as having to
       be re-calculated per spectrum.

    Returns
    -------
    mdls: list of ModelDefinition objects
       Any problematic models (for converting to Python code for
       Sherpa) have been removed. The output can be an empty list.
    """

    # Strip out models that call the same function. This is a somewhat
    # odd check, and could perhaps be done after other checks, but I
    # do it first. It could just ignore those models for which the
    # number of parameters is different, but as in that case it's
    # really just an alias for the model it doesn't seem worth it,
    # and better to skip the possible error.
    #
    # This was added to handle processing the X-Spec model file from 12.8.2,
    # which has the eplogpar model (2 params) calling the logpar model -
    # presumably by accident (bug report has been sent to Keith, and it
    # has been fixed in a patch to the 12.8.2 series) - which
    # accepts 3 parameters. Since the wrapper code includes an invariant on
    # the number of parameters, this would complicate things, so for now
    # exclude them.
    #
    funcnames = {}
    for mdl in mdls:
        try:
            funcnames[mdl.funcname] += 1
        except KeyError:
            funcnames[mdl.funcname] = 1

    invalidnames = [k for k, v in funcnames.iteritems() if v > 1]
    if len(invalidnames) > 0:
        okay_mdls = []
        for mdl in mdls:
            if mdl.funcname in invalidnames:
                info("Skipping model {} as it calls {} which is used by {} different models".format(mdl.name, mdl.funcname, funcnames[mdl.funcname]))
            else:
                okay_mdls.append(mdl)

        mdls = okay_mdls

    # Strip out unsupported models
    okay_mdls = []
    for mdl in mdls:
        if mdl.modeltype in ['Mix', 'Acn']:
            info("Skipping {} as model type = {}".format(mdl.name, mdl.modeltype))
            continue

        # The following check should never fire, but leave in
        if mdl.language not in [ModelLanguage.FORTRAN_STYLE,
                                ModelLanguage.FORTRANDP_STYLE,
                                ModelLanguage.C_STYLE,
                                ModelLanguage.CPP_STYLE]:
            langname = ModelLanguage.labels[mdl.language]
            info("Skipping {} as language = {}".format(mdl.name, langname))
            continue

        if not allow_per_spectrum_models and len(mdl.flags) > 1 \
           and mdl.flags[1] == 1:
            info("Skipping model {} as it needs to be re-evaluated per spectrum.".format(mdl.name))
            continue

        if len(mdl.flags) > 0 and mdl.flags[0] == 1:
            warn("model {} has the error flag set.".format(mdl.name))

        okay_mdls.append(mdl)

    return okay_mdls


def simple_wrap(modelname, modulename, mdl):
    """Create the Python class wrapping this model.

    This is not expected to be called directly.

    Parameters
    ----------
    modelname: str
       The name of the parent class for the model.
    modulename: str
       The name of the Python module containing the Python wrapper
       to the model function (C/C++ module).
    mdl: an instance of ModelDefinition
       The model being created.

    Returns
    -------
    code: str
       The Python code used to represent this model.
    """

    debug(" - model={}.{} type={}".format(modulename,
                                          mdl.name,
                                          modelname))

    t1 = ' ' * 4
    t2 = ' ' * 8
    out = "class {}(XS{}):\n".format(mdl.clname, modelname)
    out += '{}"""The Xspec model {}"""\n'.format(t1, mdl.name)
    # TODO: does modulename really need a _ added to it hee?
    out += "{}_calc = _{}.{}\n".format(t1, modulename, mdl.funcname)

    out += "\n"
    out += "{}def __init__(self, name='{}'):\n".format(t1, mdl.name)
    parnames = []
    for par in mdl.pars:
        out += "{}self.{} = {}\n".format(t2, par.name, par.param_string())
        parnames.append("self.{}".format(par.name))

    assert len(parnames) > 0, \
        'Expected at least 1 parameter for {} model'.format(modelname)
    if len(parnames) == 1:
        pstr = "({},)".format(parnames[0])
    else:
        pstr = "({})".format(",".join(parnames))

    # warn about untested models?
    nflags = len(mdl.flags)
    if nflags > 0:
        if mdl.flags[0] == 1:
            out += "{}warnings.warn('support for models like {} (variances are calculated by the model) is untested.')\n".format(t2, mdl.clname.lower())

        if nflags > 1 and mdl.flags[1] == 1:
            out += "{}warnings.warn('support for models like {} (recalculated per spectrum) is untested.')\n".format(t2, mdl.clname.lower())

    out += "{}XS{}.__init__(self, name, {})\n".format(t2, modelname, pstr)
    out += "\n\n"
    return out


def additive_wrap(modulename, mdl):
    """Return a string representing the Python code used to wrap
    up access to an Additive user model.
    """

    return simple_wrap('AdditiveModel', modulename, mdl)


def multiplicative_wrap(modulename, mdl):
    """Return a string representing the Python code used to wrap
    up access to an Multiplicative user model.
    """

    return simple_wrap('MultiplicativeModel', modulename, mdl)


# NOTE: at present convolution models are not supported at the
#       Python layer. See
#       https://github.com/sherpa/sherpa/issues/68
#
# def convolution_wrap(modulename, mdl):
#     """Return a string representing the Python code used to wrap
#     up access to a Convolution user model.
#     """
#
#     out = simple_wrap('ConvolutionUserKernel', modulename, mdl)
#     out += """
# def load_{0}(name):
#    "Create an instance of the X-Spec convolution model {0}"
#    xsm.load_xsconvolve({1}, name)
#
# """.format(mdl.name, mdl.clname)
#     return out


def model_to_python(modulename, mdl):
    """Return a string representing the Python code used to wrap
    up access to the given user model.

    The return value is a string.
    """

    if mdl.modeltype == "Add":
        return additive_wrap(modulename, mdl)

    elif mdl.modeltype == "Mul":
        return multiplicative_wrap(modulename, mdl)

    elif mdl.modeltype == "Con":
        # For now there is no Python code for the convolution models
        # return convolution_wrap(modulename, mdl)
        return ''

    else:
        raise ValueError("No wrapper for model={} type={}".format(mdl.name, mdl.modeltype))

_fortran_funcargs = ", ".join(["float* ear",
                               "int* ne",
                               "float* param",
                               "int* ifl",
                               "float* photar",
                               "float* photer"])

_fortrandp_funcargs = ", ".join(["double* ear",
                                 "int* ne",
                                 "double* param",
                                 "int* ifl",
                                 "double* photar",
                                 "double* photer"])

_c_funcargs = ", ".join(["const Real* energy",
                         "int Nflux",
                         "const Real* parameter",
                         "int spectrum",
                         "Real *flux",
                         "Real *fluxError",
                         "const char* init"])

_cpp_funcargs = ", ".join(["const RealArray& energy",
                           "const RealArray& parameter",
                           "int spectrum",
                           "RealArray& flux",
                           "RealArray &fluxError",
                           "const string& init"])


def model_to_include(mdl):
    """Create the include statement needed by C/C++ API.

    Parameters
    ----------
    mdel : a ModelDefinition object

    Returns
    -------
    inccode : str
       The code needed to define the function in the extern block
       of the C/C++ API.
    """

    funcname = mdl.funcname

    if mdl.language == ModelLanguage.FORTRAN_STYLE:
        args = _fortran_funcargs
        funcname += "_"

    elif mdl.language == ModelLanguage.FORTRANDP_STYLE:
        args = _fortrandp_funcargs
        funcname += "_"

    elif mdl.language == ModelLanguage.C_STYLE:
        args = _c_funcargs

    elif mdl.language == ModelLanguage.CPP_STYLE:
        # Instead of using the C++ interface, use the C style one
        # args = _cpp_funcargs
        args = _c_funcargs

    else:
        # TODO: provide a more informative error message
        raise ValueError("Unsupported language: {}".format(mdl.language))

    return "void {}({});\n".format(funcname, args)


def model_to_wrap(mdl):
    """Create the Python wrapper code needed by C/C++ API.

    Parameters
    ----------
    mdel : a ModelDefinition object

    Returns
    -------
    wrapcode : str
       The code needed to create a wrapper function for the C/C++ API.
    """

    return "    {},\n".format(mdl.make_wrapper())


def make_code(modulename, mdls):
    """Return the code needed to represent the models.

    Parameters
    ----------
    modulename: str
       The name of the Python module containing the wrappers
       to the model functions (C/C++ module).
    mdls: list of ModelDefinition objects
       The output of parse_model_file() passed through verify_models().

    Returns
    -------
    (pycode, inccode, wrapcode): (str, str, str)
       The Python code used to create model instances, the definitions
       used (for C/C++ interface), and the wrapper code around each
       model (for C/C++ interface).

    """

    pycode = ""
    inccode = ""
    wrapcode = ""

    mnames = []
    for mdl in mdls:
        debug(" - processing model {}".format(mdl.name))

        # TODO: should there be a more-extensive naming scheme, and
        #       should this error out?
        lname = mdl.clname.lower()
        if lname == modulename:
            pstr = "model class {} has the same name as the module, which may cause problems".format(mdl.clname)
            warn(pstr)

        pymodstr = model_to_python(modulename, mdl)
        if pymodstr is None:
            pstr = "Unable to convert {} to Python code".format(lname)
            warn(pstr)
            continue

        pycode += pymodstr
        inccode += model_to_include(mdl)
        wrapcode += model_to_wrap(mdl)

        mnames.append(mdl.clname)

        # The following is just to warn if an unsupported feature is being
        # used.
        nflags = len(mdl.flags)
        if nflags == 0:
            continue

        debug(" - at least one model flag; [0] = {}".format(mdl.flags[0]))
        if mdl.flags[0] == 1:
            warn("model {} calculates model variances; this is untested/unsupported in Sherpa".format(mdl.name))

        if nflags > 1 and mdl.flags[1] == 1:
            warn("model {} needs to be re-calculated per spectrum; this is untested.".format(mdl.name))

    return (pycode, inccode, wrapcode)


def write_code(infile, filehead,
               modulename='xspec',
               namefunc=add_xs_prefix,
               nametranslate=convert_parname):
    """Create code fragments.

    Parameters
    ----------
    infile: str
       The name of the Xspec model definition file to process
       (should include path, expected to be called model.dat).
    filehead: str
       Three files are created: filehead + '.py.incl',
       filehead + '.declare.incl', and filehead + '.methoddef.incl'
    modulename: str, optional
       The name of the module containing the code (expect to have
       the compiled code accessible via modulename._modulename).
    namefunc: optional
       The namefunc routine takes the model name (taken from the
       Xspec file) and returns the Python class name for the
       model; at the least it should ensure the first character
       is capitalized. The default is to prepend with XS, which
       means that a user would create an instance of the model
       foobar with xsfoobar.mdl, and the class would be called
       XSfoobar.
    nametranslate: optional
       Used to convert from the Xspec name to a name that can be used
       in Sherpa (i.e. matches Python naming rules).
    """

    mdls = parse_model_file(infile,
                            namefunc=namefunc,
                            nametranslate=nametranslate)
    if mdls == []:
        raise IOError("No models read from {}".format(infile))

    mdls = verify_models(mdls)
    if mdls == []:
        raise IOError("After cleaning, no models left in {}".format(infile))

    (pycode, dcode, mcode) = make_code(modulename, mdls)

    open("{}.py.incl".format(filehead), "w").write(pycode)
    open("{}.declare.incl".format(filehead), "w").write(dcode)
    open("{}.methoddef.incl".format(filehead), "w").write(mcode)
    print("Created: {}.py/declare/methoddef.incl".format(filehead))


if __name__ == "__main__":

    import sys
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: {} <model.dat> <outhead>\n".format(sys.argv[0]))
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    write_code(sys.argv[1], sys.argv[2])
