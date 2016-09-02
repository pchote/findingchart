#
# findingchart is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# findingchart is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with findingchart.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=invalid-name

import argparse
import base64
import datetime
import io
import math
import urllib.request
import numpy
import os
import sys
from PIL import Image, ImageOps
from astropy import wcs
from astropy.io import fits
from flask import abort
from flask import Flask
from flask import jsonify
from flask import render_template
from flask import request
import sep

def estimate_half_radius(image, fallback):
    """Estimates the half-width at half maximum
       returns fallback if it can't identify at least 10 sources"""
    bkg = sep.Background(image)
    subtracted = image - bkg

    thresh = 5 * bkg.globalrms
    raw_objects = sep.extract(subtracted, thresh)
    radius = []
    for star in raw_objects:
        # Discard spuriously small sources
        if star['npix'] < 16:
            continue

        x = star['x']
        y = star['y']
        a = star['a']
        b = star['b']
        theta = star['theta']
        kronrad, flag = sep.kron_radius(subtracted, x, y, a, b, theta, 6.0)
        if flag != 0:
            continue

        flux, _, flag = sep.sum_ellipse(subtracted, x, y, a, b, theta, 2.5 * kronrad,
                                        subpix=0)
        if flag != 0:
            continue

        r, flag = sep.flux_radius(subtracted, x, y, 6.0 * a, 0.5, normflux=flux, subpix=5)
        if flag != 0:
            continue

        radius.append(r)

    # Require at least 10 objects for a more robust estimation
    if len(radius) > 10:
        return numpy.median(radius)

    return fallback

def rescale_image_data(data, clip_low, clip_high):
    """ Returns a normalised array where clip_low percent of the pixels are 0 and
        clip_high percent of the pixels are 255
    """
    high = numpy.percentile(data, clip_high)
    low = numpy.percentile(data, clip_low)
    scale = 255. / (high - low)
    data = numpy.clip(data, low, high)
    return 255 - scale * (data - low)

def parse_sexagesimal(string):
    """Converts a sexagesimal string to decimal"""
    parts = string.split(':')
    if len(parts) != 3:
        raise ValueError('Invalid input: ' + string)

    a = float(parts[0])
    b = math.copysign(float(parts[1]), a)
    c = math.copysign(float(parts[2]), a)

    return a + b / 60 + c / 3600

def sexagesimal(angle):
    """Formats a decimal number in sexagesimal format"""
    negative = angle < 0
    angle = abs(angle)

    degrees = int(angle)
    angle = (angle - degrees) * 60
    minutes = int(angle)
    seconds = (angle - minutes) * 60

    if negative:
        degrees *= -1

    return '{:d}:{:02d}:{:05.2f}'.format(degrees, minutes, seconds)
def offset_proper_motion(ra_degrees, dec_degrees, pm_ra_degrees, pm_dec_degrees, delta_yr):
    ra = ra_degrees + float(pm_ra_degrees) / math.cos(dec_degrees * math.pi / 180) * delta_yr
    dec = dec_degrees + float(pm_dec_degrees) * delta_yr
    return (ra, dec)

def generate_finding_chart(out_year, in_ra, in_dec, in_year, ra_pm, dec_pm, width, height, survey):
    ra_j2000_degrees = parse_sexagesimal(in_ra) * 15
    dec_j2000_degrees = parse_sexagesimal(in_dec)
    ra_pm_degrees = float(ra_pm) / 3600
    dec_pm_degrees = float(dec_pm) / 3600

    ra_target, dec_target = offset_proper_motion(ra_j2000_degrees, dec_j2000_degrees,
                                                 ra_pm_degrees, dec_pm_degrees,
                                                 float(out_year) - float(in_year))
    url = 'http://archive.stsci.edu/cgi-bin/dss_search?r=' + str(ra_target) + '&dec=' + str(dec_target) \
        + '&v=' + survey + '&f=dss1&s=on&e=J2000&h=' + str(height) + '&w=' + str(width)
    filename, _ = urllib.request.urlretrieve(url)

    try:
        with fits.open(filename) as hdulist:
            frame = hdulist[0]

            # Headers can contain bogus time values (e.g. 93 minutes), so only consider year part
            frame_date = datetime.datetime.strptime(frame.header['DATE-OBS'][0:11], '%Y-%m-%dT')
            frame_year = (float(frame_date.strftime("%j"))-1) / 366 + float(frame_date.strftime("%Y"))
            delta_years = frame_year - 2000

            frame_coords = offset_proper_motion(ra_j2000_degrees, dec_j2000_degrees,
                                                       ra_pm_degrees, dec_pm_degrees,
                                                       float(frame_year) - float(in_year))

            w = wcs.WCS(hdulist[0].header)
            old_x, old_y = w.wcs_world2pix(numpy.array([frame_coords], numpy.float_), 0, ra_dec_order=True)[0]
            new_x, new_y = w.wcs_world2pix(numpy.array([[ra_target, dec_target]], numpy.float_), 0, ra_dec_order=True)[0]

            fluxrad = estimate_half_radius(frame.data.astype(float), 2)
            scaled = rescale_image_data(frame.data, 1, 99.5)
            png = ImageOps.flip(Image.fromarray(scaled).convert('RGB').resize((512, 512), Image.BICUBIC))
            scale_x = float(png.width) / scaled.shape[0]
            scale_y = float(png.height) / scaled.shape[1]
            indicator_size = 3 * fluxrad * scale_x

            # Generate JSON output
            output = io.BytesIO()
            png.save(output, format='PNG')
            output.seek(0)
            return jsonify(
                ra=sexagesimal(ra_target / 15),
                dec=sexagesimal(dec_target),
                data_pos=[old_x * scale_x, 512 - old_y * scale_y],
                observing_pos=[new_x * scale_x, 512 - new_y * scale_y],
                indicator_size=indicator_size,
                data='data:image/png;base64,' + base64.b64encode(output.read()).decode())
    finally:
        os.remove(filename)

app = Flask(__name__)

@app.route('/')
def input_display():
    return render_template('input.html')

@app.route('/generate')
def generate_chart_json():
    try:
        return generate_finding_chart(request.args['outepoch'], request.args['ra'], request.args['dec'], request.args['epoch'], request.args['rapm'], request.args['decpm'], request.args['size'], request.args['size'], request.args['survey'])
    except Exception as e:
        abort(500)
