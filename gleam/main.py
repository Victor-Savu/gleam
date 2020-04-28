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
    spectrum_file,
    target,
    inspect,
    fix_center,
    constrain_center,
    verbose,
    bin1,
):
    """
    For a target/galaxy, read the spectrum and perform the line fitting for each 
    line within the list of lines
    Input:
        spectrum_path: location on disk (folder) of the target spectrum 
        target: Astropy row with target properties 
        inspect: if true, show the plots; otherwise write to disk
        fix_center: fix the centers of the Gaussians to the lab value of the
                    emission line
        constrain_center: constrain the centers of the Gaussian to a small 
                          region around the expected lab wavelength of the line
        verbose: verbose output of warnings and line fit results
        bin1: number of adjacent spectral pixels to be binned
    Output:
        fits of emission lines and plots for each fitted lines
    """

    data_path = os.path.dirname(spectrum_file)
    print(
        f"Now working in {data_path} "
        + f'on {target["Sample"]} '
        + f'on source {target["SourceNumber"]} at z={target["Redshift"]:1.3f} '
        + f'of type {target["Type"]}\n'
    )

    # Read spectrum for the current source from outside file
    spectrum = QTable.read(spectrum_file)

    if bin1 > 1:
        spectrum = so.bin_spectrum(spectrum, bin1)

    # Given its redshift, calculate restframe spectrum
    spectrum = so.add_restframe(spectrum, target["Redshift"])

    # Configuration for curret source
    config = c(target["Setup"])

    # Read in line table
    line_list = config.line_list

    # Read in file with sky bands
    sky = config.sky_list

    # Find groups of nearby lines in the input table that will be fit together
    line_groups = so.group_lines(line_list, config.fitting.tolerance)

    with pg.overview_plot(
        target,
        data_path,
        line_groups,
        spectrum,
        config.fitting.cont_width,
        config.resolution / (1 + target["Redshift"]),
        sky,
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
            sky,
            config.fitting.tolerance,
            config.fitting.cont_width,
            config.fitting.mask_width,
            config.fitting.w,
            config.fitting.fwhm_min,
            config.fitting.fwhm_max,
            config.fitting.SN_limit,
            config.resolution / (1 + target["Redshift"]),
            config.cosmology.cosmo,
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
                line_list["wavelength"],
                lines["wavelength"],
                inspect,
                config.fitting.cont_width,
                config.resolution / (1 + target["Redshift"]),
                sky,
            )
            if spectrum_fit is not None:
                for (line_fit, line) in zip(spectrum_fit.lines, lines):
                    tables.append(
                        Table(line_fit.as_fits_table(line), masked=True, copy=False)
                    )
                plot_line(
                    lines,
                    spectrum_fit,
                    config.resolution / (1 + target["Redshift"]),
                    sky,
                )

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
