
import unittest
import sys
import os
import re

# Insert Path for project ../ from here
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from pcb_drill_gcode import PcbDrillGCode

def sample_holes():
    """ Return a list of predefined drill points"""
    holes = [(136.8190476190476, 192.18095238095236),
        (89.0, 49.5),
        (89.0, 36.5),
        (127.30701754385963, 199.39473684210526),
        (248.39473684210526, 54.307017543859644),
        (194.5, 186.24166666666665),
        (271.2416666666667, 170.5),
        (255.5, 60.24166666666666),
        (175.3095238095238, 85.5),
        (69.62015503875969, 146.62015503875966),
        (38.57364341085271, 89.15503875968992),
        (48.378787878787875, 89.11363636363636),
        (175.37878787878788, 75.88636363636364),
        (194.4518518518518, 75.96296296296296),
        (204.0, 170.59420289855072),
        (50.5, 146.5),
        (261.5, 98.5),
        (242.5, 98.5),
        (194.5, 85.5)]
    return holes

class TestPcbDrillGCode(unittest.TestCase):
    def setUp(self):
        self.holes = sample_holes()

    def test_full_gcode(self):
        """ Makes sure that the generator produces some output"""
        gcode_generator = PcbDrillGCode()
        gcode_generator.drill_holes(self.holes)
        output = gcode_generator.generate()
        self.assertTrue(len(output) > 0)

    def test_for_proper_gcode_setup(self):
        """ Ensure that we get a proper setup
        (e.g. metric mode, absolute mode, and go to home)"""
        gcode_generator = PcbDrillGCode()
        gcode_generator.drill_holes(self.holes)
        output = gcode_generator.generate()
        self.assertTrue(output.find("G21") >= 0)
        self.assertTrue(output.find("G90") >= 0)
        self.assertTrue(output.find("G28 X0 Y0") >= 0)

    def test_holes(self):
        """ Ensure that we actually have output for each of the holes"""
        gcode_generator = PcbDrillGCode()
        gcode_generator.drill_holes(self.holes)
        output = gcode_generator.generate()
        hole_count = len(self.holes)
        drill_count = 0
        
        for line in output.splitlines():
            match = re.search(r'G1 X *([\d\.]+) Y *([\d\.]+)', line)
            if match is not None:
                line_x = match.group(1)
                line_y = match.group(2)

                self.assertAlmostEqual(float(line_x), self.holes[drill_count][0])
                self.assertAlmostEqual(float(line_y), self.holes[drill_count][1])
                drill_count += 1
        self.assertEquals(hole_count, drill_count)
