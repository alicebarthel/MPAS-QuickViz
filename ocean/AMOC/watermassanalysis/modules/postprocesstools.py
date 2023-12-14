#!/usr/bin/env python
"""
    Name: postprocesstools.py
    Author: Ben Moore-Maley (bmoorema@lanl.gov)

    Shared tools for model results postprocessing
    for the ImPACTS Water Mass Analysis project.
"""

import numpy as np
import xarray as xr
import pandas as pd
import os
import time
import yaml
import pyremap
from copy import deepcopy


def loopstatus(k, n, starttime, interval=1):
    """Print loop progress at percentage intervals given an iteration k
    and a total number of iterations n
    """
    
    nscale = 100 / n
    percent = k * nscale
    if percent % interval < nscale:
        time_elapsed = time.time() - starttime
        msg = f'{int(percent)}% complete ... {time_elapsed:.0f} seconds elapsed'
        print(msg, flush=True)


def build_savepath_from_file(filein, desc, timerange=None, outdir=''):
    """Returns a `savepath` given a `filein`, `desc`, `timerange` and `outdir`.
    """
    
    # Parse filename
    path, prefix = os.path.split(filein)
    path = os.path.join(os.path.split(path)[0], outdir)
    prefix, tstr = prefix.split('.')[:2]
    mesh = prefix.split('_')[-1]
    
    # Parse tstr from timerange or filein
    if timerange is not None:
        tstr = '_'.join(date.strftime('%Y%m%d') for date in timerange)
    else:
        tstr = '_'.join(tstr.split('_')[-2:])
    
    # Build savepath
    savepath = os.path.join(path, f'{prefix}.{desc}_{tstr}.nc')
    
    return savepath, mesh


def build_remapper(
    meshfile, bbox=None,
    mapping_path='/global/cfs/cdirs/m4259/mapping_files/',
):
    """Build a `pyremap.Remapper` object for the requested mesh. Hardcoded
    to use an existing mapping file to 0.5x0.5degree. Also constructs
    a full domain dataset with the requested varnames initialized to zeros.
    """
    
    # Parse mesh name from meshfile
    meshName = meshfile.split('/')[-2]
    
    # Build remapper arguments
    meshdescriptor = pyremap.MpasMeshDescriptor(meshfile, meshName)
    lonlatdescriptor = pyremap.get_lat_lon_descriptor(dLon=0.5, dLat=0.5)
    mappingfile = os.path.join(mapping_path, f'map_{meshName}_to_0.5x0.5degree_bilinear.nc')
    
    # Build zeros array to full domain size
    with xr.open_dataset(meshfile) as ds:
        zeros = np.zeros(len(ds.nCells))

    # Define remap variables as dict
    remapvars = {
        'da_full': xr.DataArray(zeros, dims='nCells'),
        'remapper': pyremap.Remapper(meshdescriptor, lonlatdescriptor, mappingfile),
        'bbox': bbox,
    }
    
    return remapvars


def remap(array_in, nCells, da_full, remapper, bbox=None):
    """Remap `da_in` to lonlat using `remapper` object. `da_in` is on a
    subdomain so it must be populated into `da_full` before remapping
    """
    
    # Remap to lonlat
    da_in = deepcopy(da_full)
    da_in.loc[nCells] = array_in
    da_out = remapper.remap(da_in)
    if bbox is not None:
        da_out = da_out.sel(lon=slice(*bbox[:2]), lat=slice(*bbox[2:]))
    
    return da_out