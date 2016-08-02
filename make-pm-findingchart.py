#!/usr/bin/env python3
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
import math
import urllib.request
import numpy
import os
import sys
from PIL import Image, ImageOps, ImageDraw, ImageFont
from astropy import wcs
from astropy.io import fits

def rescale_image_data(data, clip_low, clip_high):
    """ Returns a normalised array where clip_low percent of the pixels are 0 and
        clip_high percent of the pixels are 255
    """
    high = numpy.percentile(data, clip_high)
    low = numpy.percentile(data, clip_low)
    scale = 255. / (high - low)
    data = numpy.clip(data, low, high)
    return scale * (data - low)

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

def generate_finding_chart(out_year, in_ra, in_dec, in_year, ra_pm, dec_pm, width, height, survey, out_path):
    circle_r = 5
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

        scaled = rescale_image_data(frame.data, 1, 99)
        png = Image.fromarray(scaled).convert('RGB').resize((512, 512), Image.BICUBIC)
        scale_x = float(png.width) / scaled.shape[0]
        scale_y = float(png.height) / scaled.shape[1]
        draw = ImageDraw.Draw(png)
        draw.ellipse((scale_x * (old_x-circle_r), scale_y * (old_y-circle_r), scale_x * (old_x + circle_r), scale_y * (old_y + circle_r)), outline='blue')
        draw.ellipse((scale_x * (new_x-circle_r), scale_y * (new_y-circle_r), scale_x * (new_x + circle_r), scale_y * (new_y + circle_r)), outline='red')
        
        png = ImageOps.flip(png)
        draw = ImageDraw.Draw(png)

        draw.rectangle((png.width - 10 - 60 * scale_x / arcsec_per_px, png.height - 20, png.width - 2, png.height - 2), 'black')
        line = (png.width - 5 - 60 * scale_x/ arcsec_per_px, png.height - 5, png.width - 5, png.height - 5)
        draw.line(line, 'white')

        font = ImageFont.truetype('DejaVuSansMono.ttf', 12)
        draw.rectangle((2,2,160,35), 'black')
        draw.text(((line[0] + line[2]) / 2 - 2, png.height - 20),"1'",'white', font=font)
        draw.text((5, 5), 'J' + out_year + '  RA: ' + sexagesimal(frame_coords[0] / 15), 'white', font=font)
        draw.text((5, 20), 'J' + out_year + ' Dec: ' + sexagesimal(frame_coords[1]), 'white', font=font)
        png.save(out_path, 'PNG', clobber=True)

    os.remove(filename)

if __name__ == '__main__':
    surveys = ['poss2ukstu_red', 'poss2ukstu_ir', 'poss2ukstu_blue', 'poss1_blue', 'poss1_red',
               'quickv', 'phase2_gsc2', 'phase2_gsc1']

    description = 'Create a blind finding chart for an object based on position and proper motion'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('out_year', help='Julian year to generate the finding chart')
    parser.add_argument('ra', help='RA of the target (in specified epoch)')
    parser.add_argument('dec', help='Dec of the target (in specified epoch)')
    parser.add_argument('epoch', help='Epoch of the target coordinates')
    parser.add_argument('pmra', help='RA Proper motion (arcsec / yr) of the target')
    parser.add_argument('pmdec', help='Dec Proper motion (arcsec / yr) of the target')
    parser.add_argument('width', help='Finding chart width (arcmin)')
    parser.add_argument('height', help='Finding chart height (arcmin)')
    parser.add_argument('survey', choices=surveys, help='Survey to use for base image')

#   TODO: argparse breaks when we pass a negative dec argument...
    args = parser.parse_args()
    generate_finding_chart(args.out_year, args.ra, args.dec, args.epoch, args.pmra, args.pmdec, args.width, args.height, args.survey, 'test.png')
#    a = sys.argv
#    generate_finding_chart(a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8], a[9], 'test.png')

