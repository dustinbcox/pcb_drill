#!/usr/bin/env python2.7

import argparse
import StringIO

# TODO read default prefix and postfix from a file

CALIBRATE_HOLES = ((0.0, 0.0), (30.0, 0.0), (0.0, 20.0))


class PcbDrillGCode(object):
    """ Generate G-Code for Drilling
        Thanks to Mike Smith who wrote the original gcode """

    def __init__(self, prefix="", postfix="", line_numbers=True, verbose_comments=True):
        """ G Code Generator
        Arguments:
            prefix - one line per gcode - prefix gcode
            postfix - one line per gcode - postfix gcode
            line_numbers - include N000 line numbers (defaults True)
            verbose_commands (defaults True) - prints additional info
        """
        self._prefix = StringIO.StringIO(prefix)
        self._postfix = StringIO.StringIO(postfix)
        self._body = None
        self._format = "G1 X{0} Y{1}"
        self._verbose_comments = verbose_comments
        self._line_numbers = line_numbers
        self._holes = []
        self._predrill_locations = []
        self._postdrill_locations = []
        self._prefix_comments = StringIO.StringIO()
        self._postfix_comments = StringIO.StringIO()

        if prefix is None or prefix == "":
            # Populate with default prefix code
            self._command(self._prefix, "G21", "metric mode")
            self._command(self._prefix, "G90", "absolute position")
            self._command(self._prefix, "G28 X0 Y0", "go home")
            self._command(self._prefix, "M42 P23 S255", "turns the spindle on")
            self._command(self._prefix, "G1 F3000", "Starting feed rate")
        elif "\n" not in prefix:
            self._prefix.write("\n")
        if postfix is None or postfix == "":
            # Populate with default postfix code
            self._command(self._postfix, "M42 P23 S0", "turns the spindle off")
            self._command(self._postfix, "G28 X0 Y0", "Go Home")
            self._command(self._postfix, "G90", "absolute position")
        elif "\n" not in postfix:
            self._postfix.write("\n")

    @property
    def prefix(self):
        return self._prefix.getvalue()
    @prefix.setter
    def prefix(self, value):
        self._prefix.truncate(size=0)
        self._prefix.write(value)
    @prefix.deleter
    def prefix(self):
        raise AttributeError("prefix cannot be deleted")

    @property
    def postfix(self):
        return self._postfix.getvalue()
    @postfix.setter
    def postfix(self, value):
        self._postfix.truncate(size=0)
        self._postfix.write(value)
    @postfix.deleter
    def postfix(self):
        raise AttributeError("postfix cannot be deleted")

    @property
    def body(self):
        if self._body is None:
            raise ValueError("You must call generate before the body property becomes available")
        else:
            return self._body
    
    def comment(self, comment):
        """ User friendly comment; guess if we want before or after drill_holes if we have holes defined"""
        if len(self._holes) == 0:
            # Assuming that we want a comment before drill holes
            self._comment(self._prefix_comments, comment)
        else:
            self._comment(self._postfix_comments, comment)

    def _comment(self, stringio_buffer, comment, inline_comment=False):
        """Add a comment ; to the gcode
        Arguments:
            inline_comment - if True then this is an inline comment with detail"""
        if comment is None or comment == "":
            return
        if inline_comment:
            # We only suppress inline comments as we consider them extraneous
            if self._verbose_comments:
                stringio_buffer.write(" ; {0}".format(comment))
        else:
            stringio_buffer.write("; {0}\n".format(comment))

    def _command(self, stringio_buffer, command, comment=""):
        stringio_buffer.write(command)
        self._comment(stringio_buffer, comment, inline_comment=True)
        stringio_buffer.write("\n")

    @property
    def drill_hole_format(self):
        return self._format
    @drill_hole_format.setter
    def drill_hole_format(self, value):
        """ drill_hole {0} {1}\n """
        self._format = value
    @drill_hole_format.deleter
    def drill_hole_format(self):
        raise AttributeError("drill_hole_format cannot be deleted")
    
    def drill_holes(self, holes):
        # TODO check type
        self._holes = holes

    def seek_predrill_location(self, location):
        self._predrill_locations.append(location)

    def seek_postdrill_location(self, location):
        self._postdrill_locations.append(location)

    def generate(self):
        gcode = StringIO.StringIO()
        self._current_line_number = 1

        prefix_location = self._prefix.tell()
        postfix_location = self._postfix.tell()
        gcode_begin_body = None
        gcode_end_body = None

        self._prefix.seek(0)
        self._postfix.seek(0)

        def write_line_number():
            """write N001 style line numbers on gcode commands"""
            if self._line_numbers:
                gcode.write("N{0:03} ".format(self._current_line_number))
                self._current_line_number += 1
        def write_area(stringio_area):
            """ Write an area such as prefix, postfix, etc."""
            for line in stringio_area.readlines():
                if line != "%\n" and not line.startswith(";"):
                    write_line_number()
                gcode.write(line)
        
        write_area(self._prefix)

        gcode_begin_body = gcode.tell()

        write_area(self._prefix_comments)

        for location in self._predrill_locations:
            write_line_number()
            self._command(gcode, self._format.format(*location), "Seek pre drill XY location")
            
        for index, hole in enumerate(self._holes):
            hole_number = index + 1
            self._comment(gcode, "--- Begin Hole # {0} at position X {1} and Y {2}".format(hole_number, hole[0], hole[1]),
                        inline_comment=False)
            write_line_number()
            self._command(gcode, self._format.format(*hole), "Drill hole location")
            write_line_number()
            self._command(gcode, "G1 Z-.5 F100", "Drill hole")
            write_line_number()
            self._command(gcode, "G1 Z3.0 F3000", "Retract drill to safe position")
            self._comment(gcode, "--- End Hole # {0}".format(hole_number,inline_comment=False))
        if len(self._holes) == 0:
            self._comment(gcode, "No Drill holes defined", inline_comment=False)

        for location in self._postdrill_locations:
            write_line_number()
            self._command(gcode, self._format.format(*location), "Seek post drill XY location")

        write_area(self._postfix_comments)

        gcode_end_body = gcode.tell()
        write_area(self._postfix)

        self._prefix.seek(prefix_location)
        self._postfix.seek(postfix_location)

        # Now grab the body section and save for the body property
        gcode.seek(gcode_begin_body)
        self._body = gcode.read(gcode_end_body - gcode_begin_body)
        
        return gcode.getvalue()


def calibrate_printer(**kwargs):
    """ Generate gcode to calibrate the "printer" """
    generator = PcbDrillGCode(**kwargs)
    generator.comment("I hope this works")
    generator.drill_holes(CALIBRATE_HOLES)
    generator.comment("That should do it")
    return generator.generate() 

def eject_bed(*args, **kwargs):
    """ Write gcode to eject bed """
    generator = PcbDrillGCode(*args,**kwargs)
    generator.comment("This will eject the bed")
    generator.seek_predrill_location((0, 180))
    return generator.generate() 

def retract_bed(*args, **kwargs):
    """ Write gcode to retract bed """
    generator = PcbDrillGCode(*args, **kwargs)
    generator.comment("This will retract the bed")
    generator.seek_predrill_location((0, 20))
    return generator.generate() 


if __name__ == "__main__":
    pass
