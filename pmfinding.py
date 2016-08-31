#
# make-pm-findingchart is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# make-pm-findingchart is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with make-pm-findingchart.  If not, see <http://www.gnu.org/licenses/>.

# pylint: disable=invalid-name

import argparse
import datetime
import io
import math
import urllib.request
import numpy
import os
import sys
from PIL import Image, ImageOps, ImageDraw, ImageFont
from astropy import wcs
from astropy.io import fits

from flask import Flask
from flask import render_template
from flask import request
from flask import send_file

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

def offset_proper_motion(ra_degrees, dec_degrees, pm_ra_degrees, pm_dec_degrees, delta_yr):
    ra = ra_degrees + float(pm_ra_degrees) / math.cos(dec_degrees * math.pi / 180) * delta_yr
    dec = dec_degrees + float(pm_dec_degrees) * delta_yr
    return (ra, dec)

def generate_finding_chart(out_year, in_ra, in_dec, in_year, ra_pm, dec_pm, width, height, survey):
    circle_r = 10
    circle_r2 = 10
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
            arcsec_per_px = frame.header['PLTSCALE'] * frame.header['XPIXELSZ'] / 1000

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

            delta_x = new_x - old_x
            delta_y = new_y - old_y
            delta_l = math.sqrt(delta_x * delta_x + delta_y * delta_y)
            dir_x = delta_x / delta_l
            dir_y = delta_y / delta_l


            scaled = rescale_image_data(frame.data, 1, 99.5)
            png = Image.fromarray(scaled).convert('RGB').resize((512, 512), Image.BICUBIC)
            scale_x = float(png.width) / scaled.shape[0]
            scale_y = float(png.height) / scaled.shape[1]

            line_start_x = old_x + circle_r2 * dir_x / scale_y
            line_start_y = old_y + circle_r2 * dir_y / scale_y
            line_end_x = new_x - circle_r * dir_x / scale_y
            line_end_y = new_y - circle_r * dir_y / scale_y

            arrow_a_x = line_end_x - 10 * (dir_y + dir_x) / scale_x
            arrow_a_y = line_end_y + 10 * (-dir_y + dir_x) / scale_y
            arrow_b_x = line_end_x - 10 * (-dir_y + dir_x) / scale_x
            arrow_b_y = line_end_y + 10 * (-dir_y - dir_x) / scale_y

            draw = ImageDraw.Draw(png)
            draw.ellipse((scale_x * new_x-circle_r, scale_y * new_y-circle_r, scale_x * new_x + circle_r, scale_y * new_y + circle_r), fill='red')
            draw.ellipse((scale_x * old_x-circle_r2, scale_y * old_y-circle_r2, scale_x * old_x + circle_r2, scale_y * old_y + circle_r2), outline='blue')

            if delta_l * scale_x > circle_r + circle_r2:
                draw.line((scale_x * line_start_x, scale_y * line_start_y, scale_x * line_end_x, scale_y * line_end_y), 'blue')
                draw.line((scale_x * arrow_a_x, scale_y * arrow_a_y, scale_x * line_end_x, scale_y * line_end_y), 'blue')
                draw.line((scale_x * arrow_b_x, scale_y * arrow_b_y, scale_x * line_end_x, scale_y * line_end_y), 'blue')

            return ImageOps.flip(png)
    finally:
        os.remove(filename)

app = Flask(__name__)

@app.route('/')
def input_display():
    return render_template('input.html')

@app.route('/generate')
def generate_chart():
    print(request.args)
    chart = generate_finding_chart(request.args['outepoch'], request.args['ra'], request.args['dec'], request.args['epoch'], request.args['rapm'], request.args['decpm'], request.args['size'], request.args['size'], request.args['survey'])
    output = io.BytesIO()
    chart.save(output, format='PNG')
    output.seek(0)

    return send_file(output, attachment_filename='chart.png', mimetype='image/png')
