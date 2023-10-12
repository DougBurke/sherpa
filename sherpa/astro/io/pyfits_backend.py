#
#  Copyright (C) 2011, 2015 - 2024
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

"""
Read and write FITS [1]_ files using the ``astropy.io.fits`` module [2]_.

References
----------

.. [1] https://en.wikipedia.org/wiki/FITS

.. [2] http://astropy.readthedocs.org/en/latest/io/fits/

"""

from contextlib import nullcontext, suppress
import logging
import os
from typing import TYPE_CHECKING, Any, Optional, Sequence, Union
import warnings

import numpy as np

from astropy.io import fits  # type: ignore
from astropy.io.fits.column import _VLF  # type: ignore
from astropy.table import Table  # type: ignore

from sherpa.io import get_ascii_data, write_arrays
import sherpa.utils  # unlike crates we do not import is_binary_file directly
from sherpa.utils.err import IOErr
from sherpa.utils.numeric_types import SherpaFloat

from .types import ColumnsType, DataType, DataTypeArg, \
    HdrType, HdrTypeArg, KeyType, NamesType, \
    HeaderItem, Header, Column, ImageBlock, TableBlock, BlockList


warning = logging.getLogger(__name__).warning
error = logging.getLogger(__name__).error

try:
    from .wcs import WCS
    HAS_TRANSFORM = True
except ImportError:
    HAS_TRANSFORM = False
    warning('failed to import WCS module; WCS routines will not be '
            'available')

__all__ = ('get_table_data', 'get_header_data', 'get_image_data',
           'get_column_data', 'get_ascii_data',
           'get_arf_data', 'get_rmf_data', 'get_pha_data',
           'pack_table_data', 'pack_arf_data', 'pack_rmf_data',
           'pack_image_data', 'pack_hdus',
           'set_table_data', 'set_image_data', 'set_pha_data',
           'set_arf_data', 'set_rmf_data', 'set_hdus')


name: str = "pyfits"
"""The name of the I/O backend."""


DatasetType = Union[str, fits.HDUList]
HDUType = Union[fits.PrimaryHDU, fits.BinTableHDU, fits.ImageHDU]


def _try_key(hdu: HDUType,
             name: str,
             *,
             fix_type: bool = False,
             dtype: type = SherpaFloat) -> Optional[KeyType]:

    value = hdu.header.get(name, None)
    if value is None:
        return None

    # TODO: As noted with the crates backend, this test is probably
    # overly broad, and we should look at simplifying it.
    #
    if str(value).find('none') != -1:
        return None

    if not fix_type:
        return value

    return dtype(value)


def _get_filename_from_hdu(hdu: fits.hdu.base._ValidHDU) -> str:
    """A filename for error reporting"""

    fobj = hdu.fileinfo()["file"]
    return "unknown" if fobj.name is None else fobj.name


def _require_key(hdu: HDUType,
                 name: str,
                 *,
                 fix_type: bool = False,
                 dtype: type = SherpaFloat) -> KeyType:
    value = _try_key(hdu, name, fix_type=fix_type, dtype=dtype)
    if value is None:
        raise IOErr('nokeyword', _get_filename_from_hdu(hdu), name)

    return value


# This is being replaced by _get_meta_data_header
#
def _get_meta_data(hdu: HDUType) -> HdrType:
    # If the header keywords are not specified correctly then
    # astropy will error out when we try to access it. Since
    # this is not an uncommon problem, there is a verify method
    # that can be used to fix up the data to avoid this: the
    # "silentfix" option is used so as not to complain too much.
    #
    hdu.verify('silentfix')

    meta = {}
    for key, val in hdu.header.items():
        meta[key] = val

    return meta


def _get_meta_data_header(hdu: fits.BinTableHDU) -> Header:
    """Retrieve the header information from the table.

    This loses the "specialized" keywords like HISTORY and COMMENT.

    """

    # If the header keywords are not specified correctly then
    # astropy will error out when we try to access it. Since
    # this is not an uncommon problem, there is a verify method
    # that can be used to fix up the data to avoid this: the
    # "silentfix" option is used so as not to complain too much.
    #
    hdu.verify('silentfix')

    out = []
    for name in hdu.header.keys():
        if name in ["", "COMMENT", "HISTORY"]:
            continue

        item = HeaderItem(name=name, value=hdu.header[name])

        comment = hdu.header.comments[name]
        if comment != '':
            # For now treat the unit as part of the comment rather
            # than try to split it out.
            #
            # item.unit = key.unit if key.unit != '' else None
            item.desc = comment

        out.append(item)

    return Header(out)


def _try_col(hdu,
             name: str,
             *,
             dtype: type = SherpaFloat,
             fix_type: bool = False) -> Optional[np.ndarray]:
    try:
        col = hdu.data.field(name)
    except KeyError:
        return None

    if isinstance(col, _VLF):
        col = np.concatenate([np.asarray(row) for row in col])
    else:
        col = np.asarray(col).ravel()

    if fix_type:
        col = col.astype(dtype)

    return col


def _try_tbl_col(hdu,
                 name: str,
                 *,
                 dtype=SherpaFloat,
                 fix_type: bool = False) -> Optional[np.ndarray]:
    try:
        col = hdu.data.field(name)
    except KeyError:
        return None

    if isinstance(col, _VLF):
        col = np.concatenate([np.asarray(row) for row in col])
    else:
        col = np.asarray(col)

    if fix_type:
        col = col.astype(dtype)

    return np.column_stack(col)


def _try_vec(hdu,
             name: str,
             *,
             dtype=SherpaFloat,
             fix_type: bool = False) -> Optional[np.ndarray]:
    try:
        col = hdu.data.field(name)
    except KeyError:
        return None

    if isinstance(col, _VLF):
        col = np.concatenate([np.asarray(row) for row in col])
    else:
        col = np.asarray(col)

    if fix_type:
        return col.astype(dtype)

    return col


def _require_col(hdu,
                 name: str,
                 *,
                 dtype: type = SherpaFloat,
                 fix_type: bool = False) -> np.ndarray:
    col = _try_col(hdu, name, dtype=dtype, fix_type=fix_type)
    if col is None:
        raise IOErr('reqcol', name, _get_filename_from_hdu(hdu))

    return col


def _require_tbl_col(hdu,
                     name: str,
                     *,
                     dtype=SherpaFloat,
                     fix_type: bool = False) -> np.ndarray:
    col = _try_tbl_col(hdu, name, dtype=dtype, fix_type=fix_type)
    if col is None:
        raise IOErr('reqcol', name, _get_filename_from_hdu(hdu))

    return col


def _require_vec(hdu,
                 name: str,
                 *,
                 dtype=SherpaFloat,
                 fix_type: bool = False) -> np.ndarray:
    col = _try_vec(hdu, name, dtype=dtype, fix_type=fix_type)
    if col is None:
        raise IOErr('reqcol', name, _get_filename_from_hdu(hdu))

    return col


def _try_col_or_key(hdu, name, *, dtype=SherpaFloat, fix_type=False):
    col = _try_col(hdu, name, dtype=dtype, fix_type=fix_type)
    if col is not None:
        return col

    return _try_key(hdu, name, fix_type=fix_type, dtype=dtype)


def _try_vec_or_key(hdu,
                    name: str,
                    size: int,
                    *,
                    dtype=SherpaFloat,
                    fix_type=False
                    ) -> Optional[np.ndarray]:
    """Return an array, even if this is a key.

    For keys, the value is replicated to the requested size.
    """
    col = _try_col(hdu, name, dtype=dtype, fix_type=fix_type)
    if col is not None:
        return col

    got = _try_key(hdu, name, fix_type=fix_type, dtype=dtype)
    if got is None:
        return None

    return np.full(size, got)


# Read Functions

# Crates supports reading gzipped files both when the '.gz' suffix
# is given and even when it is not (i.e. if you ask to load 'foo.fits'
# and 'foo.fits.gz' exists, then it will use this). This requires some
# effort to emulate with the astropy backend.

def _infer_and_check_filename(filename: str) -> str:
    if os.path.exists(filename):
        return filename

    gzname = f"{filename}.gz"
    if os.path.exists(gzname):
        return gzname

    # error message reports the original filename requested
    raise IOErr('filenotfound', filename)


def is_binary_file(filename: str) -> bool:
    """Do we think the file contains binary data?

    Notes
    -----
    This is a wrapper around the version in sherpa.utils which
    attempts to transparently support reading from a `.gz`
    version if the input file name does not exist.
    """
    fname = _infer_and_check_filename(filename)
    return sherpa.utils.is_binary_file(fname)


def open_fits(filename: str) -> fits.HDUList:
    """Try and open filename as a FITS file.

    Parameters
    ----------
    filename : str
       The name of the FITS file to open. If the file
       can not be opened then '.gz' is appended to the
       name and the attempt is tried again.

    Returns
    -------
    out
       The return value from the `astropy.io.fits.open`
       function.
    """
    fname = _infer_and_check_filename(filename)

    # With AstroPy v4.2.1 we start to see warnings when this call
    # fails (i.e. when the argument is not a FITS file).  This leads
    # to spurious messages to the user, so we just remove all
    # warnings. This may need tweaking at some point: ideally we would
    # only want to hide the warnings when it is not a FITS file but
    # show them when it is a FITS file.
    #
    # Note that this is not thread safe.
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', module='astropy.io.fits')
        try:
            return fits.open(fname)
        except OSError as oe:
            raise IOErr('openfailed', f"unable to open {fname}: {oe}") from oe


def read_table_blocks(arg: DatasetType,
                      make_copy: bool = False
                      ) -> tuple[str,
                                 dict[int, ColumnsType],
                                 dict[int, HdrType]]:
    """Read in tabular data with no restrictions on the columns."""

    # This sets nobinary=True to match the original version of
    # the code, which did not use _get_file_contents.
    #
    cm, filename = _get_file_contents(arg, exptype="BinTableHDU",
                                      nobinary=True)

    cols: dict[int, ColumnsType] = {}
    hdr: dict[int, HdrType] = {}

    with cm as hdus:
        for blockidx, hdu in enumerate(hdus, 1):
            hdr[blockidx] = {}
            header = hdu.header
            if header is not None:
                for key in header.keys():
                    hdr[blockidx][key] = header[key]

            # skip over primary, hdu.data is None

            cols[blockidx] = {}
            recarray = hdu.data
            if recarray is not None:
                for colname in recarray.names:
                    cols[blockidx][colname] = recarray[colname]

    return filename, cols, hdr


# The return value (first argument) is actually
#    fits.HDUList | nullcontext[fits.HDUList]
# but it's not obvious how to type this sensibly, so for now
# use Any instead.
#
def _get_file_contents(arg: DatasetType,
                       exptype: str = "PrimaryHDU",
                       nobinary: bool = False
                       ) -> tuple[Any, str]:
    """Read in the contents if needed.

    Set nobinary to True to avoid checking that the input
    file is a binary file (via the is_binary_file routine).
    Is this needed?

    The returned fits.HDUList should be used as a context manager,
    since that will then close the value **if needed**.

    Example
    -------

    The file will be closed after the with loop if arg is a
    string, but not if it's a astropy.io.fits object:

    >>> cm, fname = _get_file_contents(arg)
    >>> with cm as hdus:
       ...

    """

    if isinstance(arg, str) and (not nobinary or is_binary_file(arg)):
        # Looks like HDUList acts as a ContextManager even though it's
        # not mentioned in the documentation.
        #
        cm = open_fits(arg)
        filename = arg

    elif isinstance(arg, fits.HDUList) and len(arg) > 0 and \
            isinstance(arg[0], fits.PrimaryHDU):
        cm = nullcontext(arg)
        filename = arg.filename()
        if filename is None:
            filename = "unknown"

    else:
        msg = f"a binary FITS table or a {exptype} list"
        raise IOErr('badfile', arg, msg)

    return (cm, filename)


def _find_binary_table(tbl: fits.HDUList,
                       filename: str,
                       blockname: Optional[str] = None) -> fits.BinTableHDU:
    """Return the first binary table extension we find. If blockname
    is not None then the name of the block has to match (case-insensitive
    match), and any spaces are removed from blockname before checking.

    Throws an exception if there isn't a matching HDU.
    """

    # This behaviour appears odd:
    # - if blockname is not set then find the first table block
    #   (this seems okay)
    # - if blockname is set then loop through the tables and
    #   find the first block which is either a table or matches
    #   blockname
    #   (why the "is table" check; why not only match the blockname?)
    #
    if blockname is None:
        for hdu in tbl:
            if isinstance(hdu, fits.BinTableHDU):
                return hdu

    else:
        blockname = blockname.strip().lower()
        for hdu in tbl:
            if hdu.name.lower() == blockname or \
                    isinstance(hdu, fits.BinTableHDU):
                return hdu

    raise IOErr('badext', filename)


def get_header_data(arg: DatasetType,
                    blockname: Optional[str] = None,
                    hdrkeys: Optional[NamesType] = None
                    ) -> HdrType:
    """Read in the header data."""

    cm, filename = _get_file_contents(arg, exptype="BinTableHDU")

    hdr = {}
    with cm as tbl:
        hdu = _find_binary_table(tbl, filename, blockname)

        if hdrkeys is None:
            hdrkeys = hdu.header.keys()

        for key in hdrkeys:
            # TODO: should this set require_type=true or remove dtype,
            # as currently it does not change the value to str.
            hdr[key] = _require_key(hdu, key, dtype=str)

    return hdr


def get_column_data(*args) -> list[np.ndarray]:
    """Extract the column data."""

    # args is passed as type list
    if len(args) == 0:
        raise IOErr('noarrays')

    cols = []
    for arg in args:
        if arg is not None and not isinstance(arg, (np.ndarray, list, tuple)):
            raise IOErr('badarray', arg)
        if arg is not None:
            vals = np.asanyarray(arg)
            for col in np.atleast_2d(vals.T):
                cols.append(col)
        else:
            cols.append(arg)

    return cols


def get_table_data(arg: DatasetType,
                   ncols: int = 1,
                   colkeys: Optional[NamesType] = None,
                   make_copy: bool = False,
                   fix_type: bool = False,
                   blockname: Optional[str] = None,
                   hdrkeys: Optional[NamesType] = None
                   ) -> tuple[list[str], list[np.ndarray], str, HdrType]:
    """Read columns."""

    cm, filename = _get_file_contents(arg, exptype="BinTableHDU")

    with cm as tbl:
        hdu = _find_binary_table(tbl, filename, blockname)
        cnames = list(hdu.columns.names)

        # Try Channel, Counts or X,Y before defaulting to the first
        # ncols columns in cnames (when colkeys is not given).
        #
        if colkeys is not None:
            colkeys = [name.strip().upper() for name in list(colkeys)]
        elif 'CHANNEL' in cnames and 'COUNTS' in cnames:
            colkeys = ['CHANNEL', 'COUNTS']
        elif 'X' in cnames and 'Y' in cnames:
            colkeys = ['X', 'Y']
        else:
            colkeys = cnames[:ncols]

        cols = []
        for name in colkeys:
            for col in _require_tbl_col(hdu, name, fix_type=fix_type):
                cols.append(col)

        hdr = {}
        if hdrkeys is not None:
            for key in hdrkeys:
                hdr[key] = _require_key(hdu, key)

    return colkeys, cols, filename, hdr


def get_image_data(arg: DatasetType,
                   make_copy: bool = False,
                   fix_type: bool = True  # Unused
                   ) -> tuple[DataType, str]:
    """Read image data."""

    cm, filename = _get_file_contents(arg)

    #   FITS uses logical-to-world where we use physical-to-world.
    #   For all transforms, update their physical-to-world
    #   values from their logical-to-world values.
    #   Find the matching physical transform
    #      (same axis no, but sub = 'P' )
    #   and use it for the update.
    #   Physical tfms themselves do not get updated.
    #
    #  Fill the physical-to-world transform given the
    #  logical-to-world and the associated logical-to-physical.
    #      W = wv + wd * ( P - wp )
    #      P = pv + pd * ( L - pp )
    #      W = lv + ld * ( L - lp )
    # Then
    #      L = pp + ( P - pv ) / pd
    # so   W = lv + ld * ( pp + (P-pv)/pd - lp )
    #        = lv + ( ld / pd ) * ( P - [ pv +  (lp-pp)*pd ] )
    # Hence
    #      wv = lv
    #      wd = ld / pd
    #      wp = pv + ( lp - pp ) * pd

    #  EG suppose phys-to-world is
    #         W =  1000 + 2.0 * ( P - 4.0 )
    #  and we bin and scale to generate a logical-to-phys of
    #         P =  20 + 4.0 * ( L - 10 )
    #  Then
    #         W = 1000 + 2.0 * ( (20-4) - 4 * 10 ) + 2 * 4 $
    #

    with cm as hdus:
        data: DataType = {}

        # Look for data in the primary or first block.
        #
        img = hdus[0]
        if img.data is None:
            img = hdus[1]
            if img.data is None:
                raise IOErr('badimg', filename)

        if not isinstance(img, (fits.PrimaryHDU, fits.ImageHDU)):
            raise IOErr("badimg", filename)

        data['y'] = np.asarray(img.data)

        if HAS_TRANSFORM:

            def _get_wcs_key(key, suffix=""):
                val1 = _try_key(img, f"{key}1{suffix}")
                if val1 is None:
                    return None

                val2 = _try_key(img, f"{key}2{suffix}")
                if val2 is None:
                    return None

                return np.array([val1, val2], dtype=SherpaFloat)

            cdeltp = _get_wcs_key('CDELT', 'P')
            crpixp = _get_wcs_key('CRPIX', 'P')
            crvalp = _get_wcs_key('CRVAL', 'P')
            cdeltw = _get_wcs_key('CDELT')
            crpixw = _get_wcs_key('CRPIX')
            crvalw = _get_wcs_key('CRVAL')

            # proper calculation of cdelt wrt PHYSICAL coords
            if cdeltw is not None and cdeltp is not None:
                cdeltw = cdeltw / cdeltp

            # proper calculation of crpix wrt PHYSICAL coords
            if (crpixw is not None and crvalp is not None and
                cdeltp is not None and crpixp is not None):
                crpixw = crvalp + (crpixw - crpixp) * cdeltp

            if (cdeltp is not None and crpixp is not None and
                crvalp is not None):
                data['sky'] = WCS('physical', 'LINEAR', crvalp,
                                  crpixp, cdeltp)

            if (cdeltw is not None and crpixw is not None and
                crvalw is not None):
                data['eqpos'] = WCS('world', 'WCS', crvalw, crpixw,
                                    cdeltw)

        data['header'] = _get_meta_data(img)
        for key in ['CTYPE1P', 'CTYPE2P', 'WCSNAMEP', 'CDELT1P',
                    'CDELT2P', 'CRPIX1P', 'CRPIX2P', 'CRVAL1P', 'CRVAL2P',
                    'EQUINOX']:
            data['header'].pop(key, None)

    return data, filename


def _is_ogip_block(hdu: HDUType,
                   bltype1: str,
                   bltype2: Optional[str] = None) -> bool:
    """Does the block contain the expected HDUCLAS1 or HDUCLAS2 values?

    If given, we need both HDUCLAS1 and 2 to be set correctly.
    """

    if _try_key(hdu, 'HDUCLAS1') != bltype1:
        return False

    if bltype2 is None:
        return True

    return  _try_key(hdu, 'HDUCLAS2') == bltype2


def get_arf_data(arg: DatasetType,
                 make_copy: bool = False
                 ) -> tuple[TableBlock, str]:
    """Read in the ARF."""

    cm, filename = _get_file_contents(arg, exptype="BinTableHDU",
                                      nobinary=True)

    with cm as arf:
        specresp = _read_arf_specresp(arf, filename)

    return specresp, filename


def _read_arf_specresp(arf: fits.HDUList,
                       filename: str) -> TableBlock:
    """Read in the SPECRESP block of the ARF."""

    # Should we do the _has_ogip_type check first and only if that
    # fails fall back to the "common" block names? Given the lack
    # of consistency in following the OGIP standards by missions
    # let's keep this ordering.
    #
    for blname in ["SPECRESP", "AXAF_ARF"]:
        if blname in arf:
            hdu = arf[blname]
            break
    else:
        try:
            hdu = arf[1]
        except IndexError:
            raise IOErr("notrsp", filename, "an ARF") from None

        if not _is_ogip_block(hdu, 'RESPONSE', 'SPECRESP'):
            raise IOErr("notrsp", filename, "an ARF") from None

    if not isinstance(hdu, fits.BinTableHDU):
        raise IOErr(f"ARF Block from {filename} is not a binary table")

    headers = _get_meta_data_header(hdu)
    cols = [copycol(hdu, filename, name, dtype=SherpaFloat)
            for name in ["ENERG_LO", "ENERG_HI", "SPECRESP"]]

    # Optional columns: either both given or none
    #
    with suppress(IOErr):
        bin_lo = copycol(hdu, filename, "BIN_LO", dtype=SherpaFloat)
        bin_hi = copycol(hdu, filename, "BIN_HI", dtype=SherpaFloat)
        cols.extend([bin_lo, bin_hi])

    return TableBlock(hdu.name, header=headers, columns=cols)


# Commonly-used block names for the MATRIX block. Only the first two
# are given in the OGIP standard.
#
RMF_BLOCK_NAMES = ["MATRIX", "SPECRESP MATRIX", "AXAF_RMF", "RSP_MATRIX"]


def _find_matrix_blocks(filename: str,
                        hdus: fits.HDUList) -> list[fits.BinTableHDU]:
    """Report the block names that contain MATRIX data in a RMF.

    Parameters
    ----------
    filename : str
    hdus : fits.HDUList

    Returns
    -------
    blocks : list of fits.BinTableHDU
       The blocks that contain the MATRIX block. It will not be empty.

    Raises
    ------
    IOErr
       No matrix block was found

    """

    # The naming of the matrix block can be complicated, and perhaps
    # we should be looking for
    #
    #    HDUCLASS = OGIP
    #    HDUCLAS1 = RESPONSE
    #    HDUCLAS2 = RSP_MATRIX
    #
    # and check the HDUVERS keyword, but it's easier just to go on the
    # name (as there's no guarantee that these keywords will be any
    # cleaner to use). As of December 2020 there is now the
    # possibility of RMF files with multiple MATRIX blocks (where the
    # EXTVER starts at 1 and then increases).
    #
    blocks = []
    for hdu in hdus:
        if hdu.name in RMF_BLOCK_NAMES or \
           _is_ogip_block(hdu, "RESPONSE", "RSP_MATRIX"):
            blocks.append(hdu)

    if not blocks:
        raise IOErr('notrsp', filename, 'an RMF')

    return blocks


def copycol(hdu: fits.BinTableHDU,
            filename: str,
            name: str,
            dtype: Optional[type] = None) -> Column:
    """Copy the column data (which must exist).

    Parameters
    ----------
    hdu : BinTableHDU
       The HDU to search.
    filename : str
       The filename from which the HDU was created. This is used for
       error messages only.
    name : str
       The column name (case insensitive).
    dtype : None or type
       The data type to convert the column values to.

    Returns
    -------
    col : Column
       The column data.

    Raises
    ------
    IOErr
       The column does not exist.

    Notes
    -----

    Historically Sherpa has converted RMF columns to double-precision
    values, even though the standard has them as single-precision.
    Using the on-disk type (e.g. float rather than double) has some
    annoying consequences on the test suite, so for now we retain this
    behaviour.

    """

    uname = name.upper()
    try:
        vals = hdu.data[uname]
    except KeyError:
        raise IOErr("reqcol", uname, filename) from None

    if dtype is not None:
        vals = vals.astype(dtype)

    # Do not expand out variable-length arrays for now.  Note that for
    # columns the unit value is stored separately from the description
    # (TUNIT versus the commenf for the TTYPE value).
    #
    colinfo = hdu.columns[uname]
    out = Column(uname, values=vals)
    if colinfo.unit is not None:
        out.unit = colinfo.unit

    # Is there a better way of finding the description than
    # manually hunting around for the TTYPE<n> description?
    #
    pos = 1 + hdu.columns.names.index(uname)
    desc = hdu.header.comments[f"TTYPE{pos}"]
    if desc != '':
        out.desc = desc

    with suppress(KeyError):
        out.minval = hdu.header[f"TLMIN{pos}"]

    with suppress(KeyError):
        out.maxval = hdu.header[f"TLMAX{pos}"]

    return out


def _read_rmf_matrix(matrix: fits.BinTableHDU,
                     filename: str) -> TableBlock:
    """Read in the given MATRIX block"""

    # Ensure we have a DETCHANS keyword
    if matrix.header.get("DETCHANS") is None:
        raise IOErr("nokeyword", filename, "DETCHANS")

    mheaders = _get_meta_data_header(matrix)
    mcols = [copycol(matrix, filename, name, dtype=dtype) for name, dtype in
             [("ENERG_LO", SherpaFloat),
              ("ENERG_HI", SherpaFloat),
              ("N_GRP", None),
              ("F_CHAN", None),
              ("N_CHAN", None),
              ("MATRIX", None)]]
    return TableBlock(matrix.name, header=mheaders, columns=mcols)


def _read_rmf_ebounds(hdus: fits.HDUList,
                      filename: str,
                      blname: str) -> TableBlock:
    """Read in the given EBOUNDS block"""

    ebounds = hdus[blname]
    if ebounds is None:
        raise IOErr(f"Unable to read {blname} from {filename}")

    if not isinstance(ebounds, fits.BinTableHDU):
        raise IOErr(f"Block {blname} from {filename} is not a binary table")

    eheaders = _get_meta_data_header(ebounds)
    ecols = [copycol(ebounds, filename, name, dtype=dtype) for name, dtype in
             [("CHANNEL", None),
              ("E_MIN", SherpaFloat),
              ("E_MAX", SherpaFloat)]]
    return TableBlock("EBOUNDS", header=eheaders, columns=ecols)


def get_rmf_data(arg: DatasetType,
                 make_copy: bool = False
                 ) -> tuple[list[TableBlock], TableBlock, str]:
    """Read in the RMF.

    Notes
    -----
    For more information on the RMF format see the `OGIP Calibration
    Memo CAL/GEN/92-002
    <https://heasarc.gsfc.nasa.gov/docs/heasarc/caldb/docs/memos/cal_gen_92_002/cal_gen_92_002.html>`_.

    """

    # Read in the columns from the MATRIX and EBOUNDS extensions.
    #
    cm, filename = _get_file_contents(arg, exptype="BinTableHDU",
                                      nobinary=True)

    with cm as rmf:
        # Find all the potential matrix blocks.
        #
        blocks = _find_matrix_blocks(filename, rmf)
        matrixes = [_read_rmf_matrix(block, filename)
                    for block in blocks]
        ebounds = _read_rmf_ebounds(rmf, filename, "EBOUNDS")

    return matrixes, ebounds, filename


def _read_pha(pha: fits.BinTableHDU,
              filename: str) -> TableBlock:
    """Read in the PHA data.

    Note that there is minimal intepretation of the data.
    """

    headers = _get_meta_data_header(pha)

    # A lot of the data is optional or checked for in the I/O layer.
    #
    # TODO: Why not read in the channels as integers?
    cols = [copycol(pha, filename, "CHANNEL", dtype=SherpaFloat)]

    # This includes values that can be scalars (i.e. keywords)
    # or columns. It also incudes non-OGIP columns used to
    # identify PHA:II data.
    #
    # NOTE: currently unsupported (and not in crates)
    #
    #    if data['syserror'] is not None:
    #         # SYS_ERR is the fractional systematic error
    #         data['syserror'] = data['syserror'] * data['counts']
    #
    for name, dtype in [("COUNTS", SherpaFloat),
                        ("RATE", SherpaFloat),
                        ("STAT_ERR", SherpaFloat),
                        ("SYS_ERR", SherpaFloat),
                        ("BIN_LO", SherpaFloat),
                        ("BIN_HI", SherpaFloat),
                        ("BACKGROUND_UP", SherpaFloat),
                        ("BACKGROUND_DOWN", SherpaFloat),
                        # Possible scalar values
                        ("GROUPING", None),
                        ("QUALITY", None),
                        ("BACKSCAL", SherpaFloat),
                        ("BACKSCUP", SherpaFloat),
                        ("BACKSCDN", SherpaFloat),
                        ("AREASCAL", SherpaFloat),
                        # PHA:II columns or scalars
                        ("TG_M", None),
                        ("TG_PART", None),
                        ("TG_SRCID", None),
                        ("SPEC_NUM", None)
                        ]:
        with suppress(IOErr):
            cols.append(copycol(pha, filename, name, dtype=dtype))

    return TableBlock(pha.name, header=headers, columns=cols)


def get_pha_data(arg: DatasetType,
                 make_copy: bool = False,
                 use_background: bool = False
                 ) -> tuple[TableBlock, str]:
    """Read in the PHA."""

    cm, filename = _get_file_contents(arg, exptype="BinTableHDU")

    with cm as pha:
        try:
            hdu = pha["SPECTRUM"]
        except KeyError:
            try:
                hdu = pha[1]
            except IndexError:
                raise IOErr("notrsp", filename, "a PHA spectrum") from None

            if not _is_ogip_block(hdu, "SPECTRUM"):
                raise IOErr("notrsp", filename, "a PHA spectrum") from None

        if use_background:
            # Used to read BKGs found in an additional block of
            # Chandra Level 3 PHA files
            for block in pha:
                if _try_key(block, 'HDUCLAS2') == 'BKG':
                    hdu = block

        block = _read_pha(hdu, filename)

    return block, filename


# Write Functions

def check_clobber(filename: str, clobber: bool) -> None:
    """Error out if the file exists and clobber is not set."""

    if clobber or not os.path.isfile(filename):
        return

    raise IOErr("filefound", filename)


def pack_table_data(blocks: BlockList) -> fits.HDUList:
    """Pack up the table data."""

    return pack_hdus(blocks)


def set_table_data(filename: str,
                   blocks: BlockList,
                   ascii: bool = False,
                   clobber: bool = False) -> None:
    """Write out the table data."""

    check_clobber(filename, clobber)

    if ascii:
        if TYPE_CHECKING:
            assert isinstance(blocks.blocks[0], TableBlock)

        block = blocks.blocks[0]
        store = []
        colnames = []
        for col in block.columns:
            store.append(col.values)
            colnames.append(col.name)

        tbl = Table(names=colnames, data=store)
        tbl.write(filename, format='ascii.commented_header',
                  overwrite=clobber)
        return

    hdu = pack_table_data(blocks)
    hdu.writeto(filename, overwrite=True)


def pack_arf_data(blocks: BlockList) -> fits.HDUList:
    """Pack the ARF"""

    return pack_hdus(blocks)


def set_arf_data(filename: str,
                 blocks: BlockList,
                 ascii: bool = False,
                 clobber: bool = False) -> None:
    """Write out the ARF"""

    set_table_data(filename, blocks, ascii=ascii, clobber=clobber)


def pack_pha_data(blocks: BlockList) -> fits.HDUList:
    """Pack the PHA"""

    return pack_hdus(blocks)


def set_pha_data(filename: str,
                 blocks: BlockList,
                 ascii: bool = False,
                 clobber: bool = False) -> None:
    """Create a PHA dataset/file"""

    set_table_data(filename, blocks, ascii=ascii, clobber=clobber)


def pack_rmf_data(blocks) -> fits.HDUList:
    """Pack up the RMF data."""

    return pack_hdus(blocks)


def set_rmf_data(filename: str,
                 blocks: BlockList,
                 clobber: bool = False) -> None:
    """Save the RMF data to disk.

    Unlike the other save_*_data calls this does not support the ascii
    argument.

    """

    check_clobber(filename, clobber)
    hdus = pack_rmf_data(blocks)
    hdus.writeto(filename, overwrite=True)


def pack_image_data(data: DataTypeArg,
                    header: HdrTypeArg) -> fits.PrimaryHDU:
    """Pack up the image data."""

    hdrlist = fits.Header()

    def _add_keyword(name: str, val: Any) -> None:
        """Add the name,val pair to hdulist."""

        name = name.upper()
        hdrlist.append(fits.Card(name, val))

    for key, value in header.items():
        if value is None:
            continue

        _add_keyword(key, value)

    # Write Image WCS Header Keys
    if data['eqpos'] is not None:
        cdeltw = data['eqpos'].cdelt
        crpixw = data['eqpos'].crpix
        crvalw = data['eqpos'].crval
        equin = data['eqpos'].equinox

    if data['sky'] is not None:
        cdeltp = data['sky'].cdelt
        crpixp = data['sky'].crpix
        crvalp = data['sky'].crval

        _add_keyword('MTYPE1', 'sky     ')
        _add_keyword('MFORM1', 'x,y     ')
        _add_keyword('CTYPE1P', 'x      ')
        _add_keyword('CTYPE2P', 'y      ')
        _add_keyword('WCSNAMEP', 'PHYSICAL')
        _add_keyword('CDELT1P', cdeltp[0])
        _add_keyword('CDELT2P', cdeltp[1])
        _add_keyword('CRPIX1P', crpixp[0])
        _add_keyword('CRPIX2P', crpixp[1])
        _add_keyword('CRVAL1P', crvalp[0])
        _add_keyword('CRVAL2P', crvalp[1])

    if data['eqpos'] is not None:
        if data['sky'] is not None:
            # Simply the inverse of read transformations in get_image_data
            cdeltw = cdeltw * cdeltp
            crpixw = (crpixw - crvalp) / cdeltp + crpixp

        _add_keyword('MTYPE2', 'EQPOS   ')
        _add_keyword('MFORM2', 'RA,DEC  ')
        _add_keyword('CTYPE1', 'RA---TAN')
        _add_keyword('CTYPE2', 'DEC--TAN')
        _add_keyword('CDELT1', cdeltw[0])
        _add_keyword('CDELT2', cdeltw[1])
        _add_keyword('CRPIX1', crpixw[0])
        _add_keyword('CRPIX2', crpixw[1])
        _add_keyword('CRVAL1', crvalw[0])
        _add_keyword('CRVAL2', crvalw[1])
        _add_keyword('CUNIT1', 'deg     ')
        _add_keyword('CUNIT2', 'deg     ')
        _add_keyword('EQUINOX', equin)

    return fits.PrimaryHDU(data['pixels'], header=fits.Header(hdrlist))


def set_image_data(filename: str,
                   data: DataTypeArg,
                   header: HdrTypeArg,
                   ascii: bool = False,
                   clobber: bool = False) -> None:
    """Write out the image data."""

    check_clobber(filename, clobber)

    if ascii:
        set_arrays(filename, [data['pixels'].ravel()],
                   ascii=True, clobber=clobber)
        return

    img = pack_image_data(data, header)
    img.writeto(filename, overwrite=True)


def set_arrays(filename: str,
               args: Sequence[np.ndarray],
               fields: Optional[NamesType] = None,
               ascii: bool = True,
               clobber: bool = False) -> None:

    # Historically the clobber command has been checked before
    # processing the data, so do so here.
    #
    check_clobber(filename, clobber)

    # Check args is a sequence of sequences (although not a complete
    # check).
    #
    try:
        size = len(args[0])
    except (TypeError, IndexError) as exc:
        raise IOErr('noarrayswrite') from exc

    for arg in args[1:]:
        try:
            argsize = len(arg)
        except (TypeError, IndexError) as exc:
            raise IOErr('noarrayswrite') from exc

        if argsize != size:
            raise IOErr('arraysnoteq')

    nargs = len(args)
    if fields is not None and len(fields) != nargs:
        raise IOErr("wrongnumcols", nargs, len(fields))

    if ascii:
        # Historically, the serialization doesn't quite match the
        # AstroPy Table version, so stay with write_arrays. We do
        # change the form for the comment line (used when fields is
        # set) to be "# <col1> .." rather than "#<col1> ..." to match
        # the AstroPy table output used for other "ASCII table" forms
        # in this module.
        #
        # The fields setting can be None here, which means that
        # write_arrays will not write out a header line.
        #
        write_arrays(filename, args, fields=fields,
                     comment="# ", clobber=clobber)
        return

    # Simplest to convert via a Table.
    #
    if fields is None:
        fieldnames = [f'COL{idx}' for idx in range(1, nargs + 1)]
    else:
        fieldnames = list(fields)

    tbl = Table(names=fieldnames, data=args)
    hdu = fits.table_to_hdu(tbl)
    hdu.name = 'TABLE'
    hdu.writeto(filename, overwrite=True)


def _add_header(hdu: HDUType,
                header: Header) -> None:
    """Add the header items to the HDU."""

    for hdr in header.values:
        card = [hdr.name, hdr.value]
        if hdr.desc is not None or hdr.unit is not None:
            comment = "" if hdr.unit is None else f"[{hdr.unit}] "
            if hdr.desc is not None:
                comment += hdr.desc
            card.append(comment)

        hdu.header.append(tuple(card))


def _create_primary_hdu(hdr: Header) -> fits.PrimaryHDU:
    """Create a PRIMARY HDU."""

    out = fits.PrimaryHDU()
    _add_header(out, hdr)
    return out


def _create_image_hdu(hdu: ImageBlock) -> fits.ImageHDU:
    """Create an Image HDU."""

    out = fits.ImageHDU(name=hdu.name, data=hdu.image)
    _add_header(out, hdu.header)
    return out


def _create_table_hdu(hdu: TableBlock) -> fits.BinTableHDU:
    """Create a Table HDU."""

    # First create a Table which handles the FITS column settings
    # correctly.
    #
    store = []
    colnames = []
    for col in hdu.columns:
        colnames.append(col.name)
        store.append(col.values)

    out = fits.table_to_hdu(Table(names=colnames, data=store))
    out.name = hdu.name
    _add_header(out, hdu.header)

    # Add any column metadata
    #
    for idx, col in enumerate(hdu.columns, 1):
        if col.unit is not None:
            out.columns[col.name].unit = col.unit

        if col.minval is not None:
            out.header.append((f"TLMIN{idx}", col.minval))

        if col.maxval is not None:
            out.header.append((f"TLMAX{idx}", col.maxval))

        if col.desc is None:
            continue

        key = f"TTYPE{idx}"
        out.header[key] = (col.name, col.desc)

    return out


def pack_hdus(blocks: BlockList) -> fits.HDUList:
    """Create a dataset."""

    out = fits.HDUList()
    if blocks.header is not None:
        out.append(_create_primary_hdu(blocks.header))

    for block in blocks.blocks:
        if isinstance(block, TableBlock):
            hdu = _create_table_hdu(block)
        elif isinstance(block, ImageBlock):
            hdu = _create_image_hdu(block)
        else:
            raise RuntimeError(f"Unsupported block: {block}")

        out.append(hdu)

    return out


def set_hdus(filename: str,
             blocks: BlockList,
             clobber: bool = False) -> None:
    """Write out multiple HDUS to a single file."""

    check_clobber(filename, clobber)
    hdus = pack_hdus(blocks)
    hdus.writeto(filename, overwrite=True)
