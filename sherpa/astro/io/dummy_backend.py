#
#  Copyright (C) 2021 - 2024
#  MIT
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
'''A dummy backend for I/O.

This backend provides no functionality and raises an error if any of
its functions are used. It is provided as a model for what routines
are needed in a backend, even if it does nothing, and to allow
`sherpa.astro.io` to be imported even if no usable backend is
available.

'''

import logging
from typing import Any, Optional, Sequence

import numpy as np

from ..data import Data1D
from .types import NamesType, HdrTypeArg, HdrType, \
    ColumnsType, ColumnsTypeArg, DataTypeArg, DataType
from .xstable import TableHDU

__all__ = ('get_table_data', 'get_header_data', 'get_image_data',
           'get_column_data', 'get_ascii_data', 'get_arf_data',
           'get_rmf_data', 'get_pha_data',
           #
           'pack_table_data', 'pack_image_data', 'pack_pha_data',
           'pack_arf_data', 'pack_rmf_data', 'pack_hdus',
           #
           'set_table_data', 'set_image_data', 'set_pha_data',
           'set_arf_data', 'set_rmf_data', 'set_hdus')


name: str = "dummy"
"""The name of the I/O backend."""


warning = logging.getLogger(__name__).warning
warning("""Cannot import usable I/O backend.
    If you are using CIAO, this is most likely an error and you should contact the CIAO helpdesk.
    If you are using Standalone Sherpa, please install astropy.""")


def get_table_data(arg,
                   ncols: int = 1,
                   colkeys: Optional[NamesType] = None,
                   make_copy: bool = True,
                   fix_type: bool = True,
                   blockname: Optional[str] = None,
                   hdrkeys: Optional[NamesType] = None
                   ) -> tuple[list[str], list[np.ndarray], str, HdrType]:
    """Read columns from a file or object.

    The columns to select depend on the ncols and colkeys arguments,
    as well as the backend.

    Parameters
    ----------
    arg
        The data to read the columns from. This depends on the
        backend but is expected to be a file name or a tabular
        data structure supported by the backend.
    ncols: int, optional
        The number of columns to read in when colkeys is not
        set (the first ncols columns are chosen).
    colkeys: sequence of str or None, optional
        If given, what columns from the table should be selected,
        otherwise the backend selects. The default is `None`.
        Names are compared using a case insensitive match.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting. The default is `True`.
    fix_type: bool, optional
        Should the returned arrays be converted to the
        `sherpa.utils.numeric_types.SherpaFloat` type. The default
        is `True`.
    blockname: str or None, optional
        The name of the "block" (HDU) to read the column data (useful
        for data structures containing multiple blocks/HDUs) or None.
        Names are compared using a case insensitive match.
    hdrkeys: sequence of str or None, optional
        If set, the table structure must contain these keys, and the
        values are returned.  Names are compared using a case
        insensitive match.

    Returns
    -------
    names, data, filename, hdr
        The column names, as a list of strings, and the data as
        a list of NumPy arrays (matching the order and length of
        the names array). The filename is the name of the file (a
        string) and hdr is a dictionary with the requested keywords
        (when hdrkeys is `None` this dictionary will be empty).

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid, or a required column or keyword
        is missing.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_header_data(arg,
                    blockname: Optional[str] = None,
                    hdrkeys: Optional[NamesType] = None
                    ) -> HdrType:
    """Read the metadata.

    Parameters
    ----------
    arg
        The data to read the header values from. This depends on the
        backend but is expected to be a file name or a data structure
        supported by the backend.
    blockname: str or None, optional
        The name of the "block" (HDU) to read the data (useful
        for data structures containing multiple blocks/HDUs) or None.
        Names are compared using a case insensitive match.
    hdrkeys: sequence of str or None, optional
        If set, the table structure must contain these keys, and the
        values are returned. Names are compared using a case
        insensitive match.

    Returns
    -------
    hdr: dict
        A dictionary with the keyword data (only the name and values
        are returned, any sort of metadata, such as comments or units,
        are not returned).

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid or a keyword is missing.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_image_data(arg,
                   make_copy: bool = True,
                   fix_type: bool = True
                   ) -> tuple[DataType, str]:
    """Read image data.

    Parameters
    ----------
    arg
        The data to read the header values from. This depends on the
        backend but is expected to be a file name or a data structure
        supported by the backend.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting. The default is `True`.
    fix_type: bool, optional
        Should the returned arrays be converted to the
        `sherpa.utils.numeric_types.SherpaFloat` type. The default
        is `True`.

    Returns
    -------
    data, filename
        The data, as a dictionary, and the filename. The keys of the
        dictionary match the arguments when creating a
        sherpa.astro.data.DataIMG object.

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid or not an image.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_column_data(*args) -> list[np.ndarray]:
    """Extract the column data.

    Parameters
    ----------
    *args
        Extract column information from each argument. It can be an
        ndarray, list, or tuple, or a data structure from the backend,
        with each argument representing a column. 2D arguments are
        separated by column.

    Returns
    -------
    data: list of ndarray
        The column data.

    Raises
    ------
    sherpa.utils.err.IOErr
        There are no arguments or an argument is not supported.

    Notes
    -----

    An argument can be None, which is just passed back to the caller.
    This means the typing rules for the function are not quite
    correct.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


# Follow sherpa.io.get_ascii_data API except that ncols defaults to 2.
#
def get_ascii_data(filename: str,
                   ncols: int = 2,
                   colkeys: Optional[NamesType] = None,
                   sep: str = ' ',
                   dstype: type = Data1D,
                   comment: str = '#',
                   require_floats: bool = True
                   ) -> tuple[list[str], list[np.ndarray], str]:
    """Read columns from an ASCII file.

    The `sep`, `dstype`, `comment`, and `require_floats` arguments
    may be ignored by the backend.

    Parameters
    ----------
    filename : str
       The name of the ASCII file to read in.
    ncols : int, optional
       The number of columns to read in (the first ``ncols`` columns
       in the file). This is ignored if ``colkeys`` is given.
    colkeys : array of str, optional
       An array of the column names to read in. The default is
       `None`.
    sep : str, optional
       The separator character. The default is ``' '``.
    dstype : data class to use, optional
       Used to check that the data file contains enough columns.
    comment : str, optional
       The comment character. The default is ``'#'``.
    require_floats : bool, optional
       If `True` (the default), non-numeric data values will
       raise a `ValueError`.

    Returns
    -------
    colnames, coldata, filename
       The column names read in, the data for the columns
       as an array, with each element being the data for the column
       (the order matches ``colnames``), and the name of the file.

    Raises
    ------
    sherpa.utils.err.IOErr
       Raised if a requested column is missing or the file appears
       to be a binary file.
    ValueError
       If a column value can not be converted into a numeric value
       and the `require_floats` parameter is `True`.


    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_arf_data(arg,
                 make_copy: bool = False
                 ) -> tuple[DataType, str]:
    """Read in the ARF.

    Parameters
    ----------
    arg
        The data to read the ARF from. This depends on the backend but
        is expected to be a file name or a data structure supported by
        the backend.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting.

    Returns
    -------
    data, filename
        The data, as a dictionary, and the filename. The keys of the
        dictionary match the arguments when creating a
        sherpa.astro.data.DataARF object.

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid or not an ARF.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_rmf_data(arg,
                 make_copy: bool = False
                 ) -> tuple[DataType, str]:
    """Read in the RMF.

    Parameters
    ----------
    arg
        The data to read the RMF from. This depends on the backend but
        is expected to be a file name or a data structure supported by
        the backend.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting.

    Returns
    -------
    data, filename
        The data, as a dictionary, and the filename. The keys of the
        dictionary match the arguments when creating a
        sherpa.astro.data.DataRMF object.

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid or not a RMF.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def get_pha_data(arg,
                 make_copy: bool = False,
                 use_background: bool = False
                 ) -> tuple[list[DataType], str]:
    """Read in the PHA.

    Parameters
    ----------
    arg
        The data to read the PHA from. This depends on the backend but
        is expected to be a file name or a data structure supported by
        the backend.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting.
    use_background: bool, optional
        Should the data be read in as a background file (only relevant
        for files that contain the background data in a separate block
        of the same file, such as Chandra Level 3 PHA files, as used
        by the Chandra Source Catalog). The default is `False`.

    Returns
    -------
    datas, filename
        A list of dictionaries, containing the PHA data (since there
        can be multiple datasets with a PHA-II file) and the filename.
        The keys of the dictionary match the arguments when creating
        a sherpa.astro.data.DataPHA object.

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid or not a PHA.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_table_data(data: ColumnsTypeArg,
                    col_names: NamesType,
                    header: Optional[HdrTypeArg] = None) -> Any:
    """Create the tabular data.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.

    Returns
    -------
    table
        A data structure used by the backend to represent tabular data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_image_data(data: DataTypeArg,
                    header: HdrTypeArg) -> Any:
    """Create the image data.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    data : dict
        The image data, where the keys are arguments used to create a
        sherpa.astro.data.DataIMG object.
    header : dict
        The header information to include.

    Returns
    -------
    image
        A data structure used by the backend to represent image data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_pha_data(data: ColumnsTypeArg,
                  col_names: NamesType,
                  header: Optional[HdrTypeArg] = None) -> Any:
    """Create the PHA.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.

    Returns
    -------
    pha
        A data structure used by the backend to represent PHA data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_arf_data(data: ColumnsTypeArg,
                  col_names: NamesType,
                  header: Optional[HdrTypeArg] = None) -> Any:
    """Create the ARF.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.

    Returns
    -------
    arf
        A data structure used by the backend to represent ARF data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_rmf_data(blocks) -> Any:
    """Create the RMF.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    blocks : sequence of pairs
        The RMF data, stored as pairs of (data, header), where data is
        a dictionary of column name (keys) and values, and header is a
        dictionary of key and values. The first element is the MATRIX
        block and the second is for the EBOUNDS block.

    Returns
    -------
    rmf
        A data structure used by the backend to represent RMF data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def pack_hdus(blocks: Sequence[TableHDU]) -> Any:
    """Create a dataset.

    .. versionadded:: 4.17.0

    Parameters
    ----------
    blocks : sequence of TableHDU
        The blocks (HDUs) to store.

    Returns
    -------
    hdus
        A data structure used by the backend to represent the data.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_table_data(filename: str,
                   data: ColumnsTypeArg,
                   col_names: NamesType,
                   header: Optional[HdrTypeArg] = None,
                   ascii: bool = False,
                   clobber: bool = False) -> None:
    """Write out the tabular data.

    .. versionchanged:: 4.17.0
       The packup argument has been removed as `pack_table_data`
       should be used instead.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.
    ascii : bool, optional
        Is the file to be written out as a text file (`True`) or a
        binary file? The default is `False`.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_image_data(filename: str,
                   data: DataTypeArg,
                   header: HdrTypeArg,
                   ascii: bool = False,
                   clobber: bool = False) -> None:
    """Write out the image data.

    .. versionchanged:: 4.17.0
       The packup argument has been removed as `pack_image_data`
       should be used instead.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    data : dict
        The image data, where the keys are arguments used to create a
        sherpa.astro.data.DataIMG object.
    header : dict
        The header information to include.
    ascii : bool, optional
        Is the file to be written out as a text file (`True`) or a
        binary file? The default is `False`.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_pha_data(filename: str,
                 data: ColumnsTypeArg,
                 col_names: NamesType,
                 header: Optional[HdrTypeArg] = None,
                 ascii: bool = False,
                 clobber: bool = False) -> None:
    """Write out the PHA.

    .. versionchanged:: 4.17.0
       The packup argument has been removed as `pack_pha_data`
       should be used instead.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.
    ascii : bool, optional
        Is the file to be written out as a text file (`True`) or a
        binary file? The default is `False`.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_arf_data(filename: str,
                 data: ColumnsTypeArg,
                 col_names: NamesType,
                 header: Optional[HdrTypeArg] = None,
                 ascii: bool = False,
                 clobber: bool = False) -> None:
    """Write out the ARF.

    .. versionchanged:: 4.17.0
       The packup argument has been removed as `pack_arf_data`
       should be used instead.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    data : dict
        The table data, where the key is the column name and the value
        the data.
    col_names : sequence of str
        The column names from data to use (this also sets the order).
    header : dict or None, optional
        Any header information to include.
    ascii : bool, optional
        Is the file to be written out as a text file (`True`) or a
        binary file? The default is `False`.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_rmf_data(filename: str,
                 blocks,
                 clobber: bool = False) -> None:
    """Write out the RMF.

    .. versionchanged:: 4.17.0
       The packup argument has been removed as `pack_rmf_data`
       should be used instead.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    blocks : sequence of pairs
        The RMF data, stored as pairs of (data, header), where data is
        a dictionary of column name (keys) and values, and header is a
        dictionary of key and values. The first element is the MATRIX
        block and the second is for the EBOUNDS block.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    Notes
    -----
    There is currently no support for writing out a RMF as an ASCII
    file.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_hdus(filename: str,
             blocks: Sequence[TableHDU],
             clobber: bool = False) -> None:
    """Write out (possibly multiple) blocks.

    Parameters
    ----------
    filename : str
        The name of the file to create.
    blocks : sequence of TableHDU
        The blocks (HDUs) to store.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def read_table_blocks(arg,
                      make_copy: bool = False
                      ) -> tuple[str,
                                 dict[int, ColumnsType],
                                 dict[int, HdrType]]:
    """Read in tabular data with no restrictions on the columns.

    Parameters
    ----------
    arg
        The data to read the columns from. This depends on the
        backend but is expected to be a file name or a tabular
        data structure supported by the backend.
    make_copy: bool, optional
        If set then the returned NumPy arrays are explictly copied,
        rather than using a reference from the data structure
        created by the backend. Backends are not required to
        honor this setting.

    Returns
    -------
    filename, blockdata, hdrdata
        The filename as a string. The blockdata and hdrdata values are
        dictionaries where the key is an integer representing the
        block (or HDU) number (where the first block is numbered 1 and
        represents the first tabular block, that is it does not
        include the primary HDU) and the values are dictionaries
        representing the column data or header data for each block.

    Raises
    ------
    sherpa.utils.err.IOErr
        The arg argument is invalid, or a required column or keyword
        is missing.

    """
    raise NotImplementedError('No usable I/O backend was imported.')


def set_arrays(filename: str,
               args: Sequence[np.ndarray],
               fields: Optional[NamesType] = None,
               ascii: bool = True,
               clobber: bool = False) -> None:
    """Write out columns.

    Parameters
    ----------
    filename : str
        The file name.
    args : sequence of ndarray
        The column data.
    fields : sequence of str or None, optional
        The column names to use. If set to `None` then the columns are
        named ``col1``, ``col2``, ...
    ascii : bool, optional
        Is the file to be written out as a text file (`True`) or a
        binary file? The default is `True`.
    clobber : bool, optional
        If the file already exists can it be over-written (`True`) or
        will a sherpa.utils.err.IOErr error be raised? The default is
        `False`.

    """
    raise NotImplementedError('No usable I/O backend was imported.')
