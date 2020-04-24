__author__ = "Andra Stroe"
__version__ = "0.1"

import os, sys

import numpy as np
import astropy
from astropy import units as u
from astropy.table import QTable, Table, Column
from astropy.io import fits
from colorama import Fore
from colorama import init

init(autoreset=True)

import gleam.read_files as rf
import gleam.gaussian_fitting as gf
import gleam.plot_gaussian as pg
import gleam.spectra_operations as so
from gleam.constants import a as c


def run_main(
    data_path,
    target,
    inspect=False,
    fix_center=False,
    constrain_center=False,
    verbose=False,
    ignore_sky_lines=False,
    bin1=1,
):
    """
    For a target/galaxy, read the spectrum and perform the line fitting for each 
    line within the list of lines
    Input:
        data_path: location on disk (folder) of the target spectrum 
        target: observed spectrum in specpro format 
        inspect: if true, show the plots; otherwise write to disk
        fix_center: fix the centers of the Gaussians to the lab value of the
                    emission line
        constrain_center: constrain the centers of the Gaussian to a small 
                          region around the expected lab wavelength of the line
        verbose: verbose output of warnings and line fit results
        ignore_sky_lines: do not mask sky lines, for cases where the processing
                          of the data was highly successful and emission lines 
                          can be recovered
        bin1: number of adjacent spectral pixels to be binned
    Output:
        fits of emission lines and plots for each fitted lines
    """
    print(
        f"Now working in {data_path} "
        + f'on {target["Sample"]} '
        + f'on source {target["SourceNumber"]} at z={target["Redshift"]:1.3f} '
        + f'of type {target["Type"]}\n'
    )

    # Read spectrum for the current source from outside file
    spectrum = QTable.read(
        "{}.fits".format(
            rf.naming_convention(
                data_path,
                target["Sample"],
                target["SourceNumber"],
                target["Setup"],
                target["Pointing"],
                "spec1d",
            )
        )
    )

    if bin1 > 1:
        spectrum = so.bin_spectrum(spectrum, bin1)

    # Given its redshift, calculate restframe spectrum
    spectrum = so.add_restframe(spectrum, target["Redshift"])

    # Read in line table
    line_list = rf.read_lol(c.setups[target["Setup"]].line_table)

    # Find groups of nearby lines in the input table that will be fit together
    line_groups = so.group_lines(line_list, c.fitting.tolerance)

    with pg.overview_plot(
        target,
        data_path,
        line_groups,
        spectrum,
        c.fitting.cont_width,
        c.fitting.spectral_resolution,
    ) as plot_line:
        tables = []
        # Set the name to the exported plot in png format
        for spectrum_fit, spectrum_line, lines in gf.fit_lines(
            target,
            spectrum,
            line_list,
            line_groups,
            fix_center,
            constrain_center,
            verbose,
            ignore_sky_lines,
            c.fitting.tolerance,
            c.fitting.cont_width,
            c.fitting.mask_width,
            c.fitting.w,
            c.fitting.fwhm_min,
            c.fitting.fwhm_max,
            c.fitting.SN_limit,
            c.fitting.spectral_resolution,
            c.cosmology.cosmo,
            c.setups[target["Setup"]].resolution,
        ):
            # Make a plot/fit a spectrum if the line in within the rest-frame
            # spectral coverage of the source
            pg.plot_spectrum(
                data_path,
                target,
                spectrum,
                spectrum_line,
                spectrum_fit,
                lines["line"],
                line_list["latex"],
                line_list["wl_vacuum"],
                lines["wl_vacuum"],
                inspect,
                c.fitting.cont_width,
                c.fitting.spectral_resolution,
            )
            if spectrum_fit is not None:
                for (line_fit, line) in zip(spectrum_fit.lines, lines):
                    tables.append(
                        Table(line_fit.as_fits_table(line), masked=True, copy=False)
                    )
                plot_line(lines, spectrum_fit, c.fitting.spectral_resolution)

    try:
        outtable = astropy.table.vstack(tables)
        outtable = Table(outtable, masked=True, copy=False)
        outfile = "{}.fits".format(
            rf.naming_convention(
                data_path,
                target["Sample"],
                target["SourceNumber"],
                target["Setup"],
                target["Pointing"],
                "linefits",
            )
        )
        outtable.write(outfile, overwrite=True)
    except:
        print(
            Fore.RED
            + "Warning: no emission line fits in source: {} {}".format(
                target["Sample"], target["SourceNumber"]
            )
        )
