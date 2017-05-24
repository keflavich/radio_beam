from astropy import units as u
from astropy.io import fits
from astropy import constants
import astropy.units as u
from astropy import wcs
from astropy.extern import six
import numpy as np
import warnings

from .beam import Beam, _to_area, SIGMA_TO_FWHM


class Beams(u.Quantity):
    """
    An object to handle a set of radio beams for a data cube.
    """
    def __new__(cls, majors=None, minors=None, pas=None,
                areas=None, default_unit=u.arcsec, meta=None):
        """
        Create a new set of Gaussian beams

        Parameters
        ----------
        major : :class:`~astropy.units.Quantity` with angular equivalency
        minor : :class:`~astropy.units.Quantity` with angular equivalency
        pa : :class:`~astropy.units.Quantity` with angular equivalency
        area : :class:`~astropy.units.Quantity` with steradian equivalency
        default_unit : :class:`~astropy.units.Unit`
            The unit to impose on major, minor if they are specified as floats
        """

        # improve to some kwargs magic later

        # error checking

        # ... given an area make a round beam assuming it is Gaussian
        if areas is not None:
            rad = np.sqrt(areas / (2 * np.pi)) * u.deg
            majors = rad * SIGMA_TO_FWHM
            minors = rad * SIGMA_TO_FWHM
            pas = np.zeros_like(areas) * u.deg

        # give specified values priority
        if majors is not None:
            if u.deg.is_equivalent(majors.unit):
                majors = majors
            else:
                warnings.warn("Assuming major axes has been specified in degrees")
                majors = majors * u.deg
        if minors is not None:
            if u.deg.is_equivalent(minors.unit):
                minors = minors
            else:
                warnings.warn("Assuming minor axes has been specified in degrees")
                minors = minors * u.deg
        if pas is not None:
            if len(pas) != len(majors):
                raise ValueError("Number of position angles must match number of major axis lengths")
            if u.deg.is_equivalent(pas.unit):
                pas = pas
            else:
                warnings.warn("Assuming position angles has been specified in degrees")
                pas = pas * u.deg
        else:
            pas = np.zeros_like(pas) * u.deg

        # some sensible defaults
        if minors is None:
            minors = majors
        elif len(minors) != len(majors):
            raise ValueError("Minor and major axes must have same number of values")

        self = super(Beams, cls).__new__(cls, _to_area(majors, minors).value, u.sr)
        self.majors = majors
        self.minors = minors
        self.pas = pas
        self.default_unit = default_unit

        if meta is None:
            self.meta = [{}]*len(self)
        else:
            self.meta = meta

        return self

    @property
    def meta(self):
        return self._meta

    @meta.setter
    def meta(self, value):
        if len(value) == len(self):
            self._meta = value
        else:
            raise TypeError("metadata must be a list of dictionaries")

    def __len__(self):
        return len(self.majors)


    @property
    def isfinite(self):
        return ((self.major > 0) & (self.minor > 0) & np.isfinite(self.major) &
                np.isfinite(self.minor) & np.isfinite(self.pa))

    def __getitem__(self, view):
        if isinstance(view, (int, slice)):
            return Beam(major=self.major[view],
                        minor=self.minor[view],
                        pa=self.pa[view],
                        meta=self.meta[view])
        elif isinstance(view, np.ndarray):
            if view.dtype.name != 'bool':
                raise ValueError("If using an array to index beams, it must "
                                 "be a boolean array.")
            return Beam(major=self.major[view],
                        minor=self.minor[view],
                        pa=self.pa[view],
                        meta=[x for ii,x in zip(view, self.meta) if ii])


    @classmethod
    def from_fits_bintable(cls, bintable):
        """
        Instantiate a Beams list from a bintable from a CASA-produced image
        HDU.

        Parameters
        ----------
        bintable : fits.BinTableHDU
            The table data containing the beam information

        Returns
        -------
        beams : Beams
            A new Beams object
        """
        majors = u.Quantity(bintable.data['BMAJ'], u.arcsec)
        minors = u.Quantity(bintable.data['BMIN'], u.arcsec)
        pas = u.Quantity(bintable.data['BPA'], u.arcsec)
        meta = [{key: row[key] for key in bintable.columns.names
                 if key not in ('BMAJ', 'BPA', 'BMIN')}
                for row in bintable.data]

        return cls(majors=majors, minors=minors, pas=pas, meta=meta)
