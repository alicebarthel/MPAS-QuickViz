#!/usr/bin/env python
"""
    Name: visualizationtools.py
    Author: Ben Moore-Maley (bmoorema@lanl.gov)

    Visualization tools for the ImPACTS Water Mass Analysis project
"""

import numpy as np
from scipy.interpolate import griddata
from dateutil.parser import parse
from matplotlib import pyplot as plt
from cartopy import crs, feature
from tqdm import tqdm
from fastjmd95 import rho


def xy2cartopy(ax, xy):
    """Convert from `xy` in axis coords to cartopy data coords
    """

    xy_cartopy = ax.transData.inverted().transform(ax.transAxes.transform(xy))

    return xy_cartopy


def get_clabel_positions(ax, points):
    """Retreive hard-coded `clabel` positions for sigma contours
    """
    
    # Parse points from dict and convert from axis coords to cartopy
    xy = [[float(val) for val in points[name].split(',')] for name in points]
    points = [xy2cartopy(ax, (x, y)) for x, y in zip(*xy)]

    return points


def parse_contour_levels(clims):
    """Parse `clims` params into arrays for setting contour levels and ticks.
    
    clims = [lower, upper, contour_inc, cbar_inc, residual_bound, contour_inc, cbar_inc]
    """
    
    # Return None if clims is None
    if clims is None:
        return None, None, None, None
    
    # Else parse contour levels and ticks
    else:
        
        # Increment to make upper bound inclusive
        i = 1e-6
    
        # Left panel
        l, u = clims[:2]
        levels1, ticks1 = [np.arange(l, u + i, d) for d in clims[2:4]]

        # Right panel
        u = clims[4]
        levels2, ticks2 = [np.arange(l, u + i, d) for l, d in zip([-u, 0], clims[5:])]
        ticks2 = np.unique(np.hstack([-ticks2, ticks2]))

    return levels1, levels2, ticks1, ticks2


def parse_timeranges(timeranges):
    """Parse a list of timerange `str` pairs into a `dict` of key, value pairs
    Returns: `dict('yyyy-yyyy': [datetime(yyyy, m, d), datetime(yyyy, m, d)], ...)`
    """
    
    # Parse timeranges to dict
    timedict = {}
    for timerange in timeranges:
        values = [parse(t) for t in timerange]
        name = '-'.join(str(t.year) for t in values)
        timedict[name] = values
    
    return timedict


def build_variables_spatial(ds, varnames, timeranges, seasons=None):
    """Prebuild plotting variables to make plotting faster. Uses
    `scipy.interpolate.griddata` for regridding.
    """
    
    # Define plotting seasons
    if seasons is None:
        seasons = ['DJF', 'MAM', 'JJA', 'SON']
    
    # Define gridded lon and lat
    lon, lat = np.arange(-100, 20, 0.1), np.arange(0, 80, 0.1)
    xi = tuple(np.meshgrid(lon, lat))
    
    # Prepare plotvars dict
    plotvars = {mesh: {} for mesh in ds}
    
    # Loop through meshes
    for mesh in ds:
        
        # Extract coords for given mesh
        x = tuple(ds[mesh][name].values for name in ('lon', 'lat'))
        
        # Loop through timeranges
        for tstr in timeranges:
            
            # Extract timerange and seasons
            ds_slc = ds[mesh].sel(time=slice(*timeranges[tstr]))
            tindex = [season in seasons for season in ds_slc.time.dt.season]
            ds_slc = ds_slc.sel(time=tindex)
            
            # Extract variables
            plotvars[mesh][tstr] = {name: ds_slc[name].mean(dim='time').values for name in varnames}
            
            # Calculate sigma
            S, T = [ds_slc[name].values for name in ('salinity', 'temperature')]
            plotvars[mesh][tstr]['sigma'] = rho(S, T, 0).mean(axis=0) - 1000
            
            # Interpolate to grid
            for name in tqdm(plotvars[mesh][tstr], desc=f'Building {mesh} {tstr}'):
                plotvars[mesh][tstr][name] = griddata(x, plotvars[mesh][tstr][name], xi)
    
    return lon, lat, plotvars


def plot_variable_spatial(plotvars, lon, lat, varname, units, scale=1, clims=None, cmap=None):
    """Plot specified variable over spatial region. Hard-coded for two timeranges,
    two meshes and the residual between meshes. These categories must be consistent
    with the structure of the `plotvars` dictionary.
    """
    
    # General definitions
    meshes, tstrs = list(plotvars), list(list(plotvars.values())[0])[::-1]
    levels1, levels2, ticks1, ticks2 = parse_contour_levels(clims)
    
    # Sigma contour level specs
    sigma_levels = {
        'levels'    : [25, 25.5, 26, 26.5, 27, 27.5],
        'linestyles': ['-', '--', '-', '--', '-', '--'],
        'colors'    : ['k', 'k', 'gray', 'gray', 'lightgray', 'lightgray'],
    }

    # Plot and panel attributes
    proj_ref = crs.PlateCarree()
    kwargs = {
        'figsize': (12, 8),
        'subplot_kw': {'projection': crs.LambertConformal(-40, 0)},
        'gridspec_kw': {'hspace': 0.05, 'wspace': 0.05},
    }
    plot_kwargs = {'extend': 'both', 'transform': proj_ref, 'zorder': 0}
    
    # Make plot area
    fig, axs = plt.subplots(2, 3, **kwargs)
    
    # Plot cartopy features
    for ax in axs.ravel():
        ax.set_extent([-80, -10, 10, 80])
        ax.add_feature(feature.LAND, color='lightgray', zorder=1)
        ax.coastlines(zorder=1)
    
    # Add titles
    for col, title in zip(axs.T, meshes + [f'{meshes[0]}-{meshes[1]}']):
        col[0].set_title(title)
    
    # Loop through time ranges
    for row, tstr in zip(axs, tstrs):
        
        # Print time range
        row[0].text(0.01, 0.8, tstr, transform=row[0].transAxes)
    
        # Loop through meshes
        for ax, mesh in zip(row, meshes):

            # Plot variable
            c1 = ax.contourf(
                lon, lat, plotvars[mesh][tstr][varname] * scale,
                levels=levels1, cmap=cmap, **plot_kwargs,
            )

            # Plot sigma contours
            cs = ax.contour(
                lon, lat, plotvars[mesh][tstr]['sigma'],
                **sigma_levels, **plot_kwargs,
            )
        
        # Plot residual
        residual = np.subtract(*[plotvars[mesh][tstr][varname] for mesh in meshes])
        c2 = row[2].contourf(
            lon, lat, residual * scale,
            levels=levels2, cmap='RdBu_r', **plot_kwargs,
        )

    # Add colorbars
    cax1 = fig.add_axes([0.13, 0.07, 0.5, 0.015])
    cax2 = fig.add_axes([0.67, 0.07, 0.21, 0.015])
    fig.colorbar(c1, cax=cax1, label=units, ticks=ticks1, orientation='horizontal')
    fig.colorbar(c2, cax=cax2, label=units, ticks=ticks2, orientation='horizontal')
    
    return fig, axs