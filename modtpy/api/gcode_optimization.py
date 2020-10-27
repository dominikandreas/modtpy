import copy
import logging
import math
import tqdm

from modtpy.api.utils import TqdmLogger


class Vec3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def __pow__(self, power):
        return Vec3(self.x ** 2, self.y ** 2, self.z ** 2)

    def _math_op(self, other, op_fun):
        if isinstance(other, Vec3):
            return Vec3(op_fun(self.x, other.x), op_fun(self.y, other.y), op_fun(self.z, other.z))
        elif isinstance(other, (int, float)):
            return Vec3(op_fun(self.x, other), op_fun(self.y, other), op_fun(self.z, other))
        elif isinstance(other, (list, tuple)):
            assert len(other) == 3
            return Vec3(op_fun(self.x, other[0]), op_fun(self.y, other[1]), op_fun(self.z, other[2]))
        else:
            raise RuntimeError("encountered invalid type for mul: %s" % type(other))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __mul__(self, other):
        return self._math_op(other, lambda x, y: x * y)

    def __sub__(self, other):
        return self._math_op(other, lambda x, y: x - y)

    def __add__(self, other):
        return self._math_op(other, lambda x, y: x + y)

    def copy(self):
        return Vec3(self.x, self.y, self.z)

    def __len__(self):
        return 3

    def __getitem__(self, item):
        return [self.x, self.y, self.z][item]

    def __setitem__(self, key, value):
        self.__setattr__("x y z".split()[key], value)

    def cross(self, other):
        return Vec3(self.y * other.z - self.z * other.y,
                    self.z * other.x - self.x * other.z,
                    self.x * other.y - self.y * other.x)

    def mag(self):
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def __str__(self):
        return "Vec3(%.4f, %.4f, %.4f)"


def sign(x):
    return -1 if x < 0 else 0 if x == 0 else 1


def mag(a):
    return math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)


indices = {'G': 0, 'F': 1, 'X': 2, 'Y': 3, 'Z': 4, 'E': 5}


class GcodeOptimizer:
    def __init__(self):
        self.nextXYZ = self.sequenceFeedrate = self.sequenceXYZ = self.sequenceExtruding = self.sequenceE = None
        self.curXYZ = Vec3(0, 0, 0)
        self.curE = self.nextE = 0
        self.newSequence = True
        self.lastF = -1

    def finish_sequence(self, XYZ, E, F):
        """ we're here because the sequence is ready to be "closed out"
         this may have happened because of a change in feed-rate, extruder behavior, a non-G1 code,
        or that the error may have been too great. regardless, it's time to finish write one line of g-code """
        result = []

        outline = 'G1'

        if self.lastF != F:
            outline = outline + ' F' + str(F)
        self.lastF = F
        if XYZ.x != self.curXYZ.x:
            outline = outline + ' X' + str(XYZ.x)
        if XYZ.y != self.curXYZ.y:
            outline = outline + ' Y' + str(XYZ.y)
        if XYZ.z != self.curXYZ.z:
            outline = outline + ' Z' + str(XYZ.z)
        if E != self.curE:
            outline = outline + ' E' + str(E)

        result.append(outline)

        self.curXYZ = XYZ.copy()
        self.curE = copy.deepcopy(E)
        return result

    def init_sequence(self, flags, args, curXYZ: Vec3, curE):

        # initialize a new sequence
        # define sequence feedrate, if it is set
        if flags[1]:
            self.sequenceFeedrate = args[1]

        # add this G-code's target to the position sequence
        self.nextXYZ = copy.deepcopy(curXYZ)
        self.nextE = copy.deepcopy(curE)

        if flags[2]:
            self.nextXYZ.x = args[2]
        if flags[3]:
            self.nextXYZ.y = args[3]
        if flags[4]:
            self.nextXYZ[2] = args[4]
        if flags[5]:
            self.nextE = args[5]

        self.sequenceXYZ = [copy.copy(self.nextXYZ)]
        self.sequenceE = [copy.copy(self.nextE)]

        # check if this sequence is moving the extruder forward, backward, or not
        if self.nextE > self.curE:
            self.sequenceExtruding = 1
        elif self.nextE < self.curE:
            self.sequenceExtruding = -1
        else:
            self.sequenceExtruding = 0

        # set the new sequence flag to false now, since we just primed a new sequence
        self.newSequence = False

    def optimize_gcode(self, gcode, error_threshold=0.15, logger=None):
        result = []

        if logger is None:
            logger = logging.getLogger()

        tqdm_out = TqdmLogger(logger)

        for this_line in tqdm.tqdm(gcode.split("\n"), file=tqdm_out, desc="Optimizing gcode"):
            # ignore empty lines
            if not this_line.strip():
                continue

            # if anything other than a G0 or G1 command, copy it after g-codes from an unfinished sequence
            # also flag that a new movement sequence needs to be started
            if not ((this_line[0:3] == 'G0 ') or (this_line[0:3] == 'G1 ')):
                if not self.newSequence:
                    result += self.finish_sequence(self.sequenceXYZ[-1], self.sequenceE[-1], self.sequenceFeedrate)

                self.newSequence = True
                result.append(this_line)

                # check for G92 line, and reset current axis positions accordingly.
                # Writing out the g-code first, if necessary
                if this_line.startswith('G92'):
                    codes = this_line.rstrip().split(' ')
                    flags = [False, False, False, False, False, False]  # GFXYZE commanded flags
                    args = [0, 0, 0, 0, 0, 0]  # GFXYZE arguments
                    for code in codes:
                        key = code[0]
                        idx = indices.get(key)
                        if idx == 2:
                            self.curXYZ.x = float(code[1:])
                        elif idx == 3:
                            self.curXYZ.y = float(code[1:])
                        elif idx == 4:
                            self.curXYZ.z = float(code[1:])
                        elif idx == 5:
                            self.curE = float(code[1:])
                continue

            # Okay, we're here for a G0 or G1 (move command). Parse it.
            # first remove trailing comments as well as leading and trailing whitespace and split into words
            codes = this_line.split(';')[0].strip().split(' ')

            flags = [False, False, False, False, False, False]  # GFXYZE commanded flags
            args = [0, 0, 0, 0, 0, 0]  # GFXYZE arguments
            for code in codes:
                key = code[0]
                idx = indices.get(key, 'default')
                flags[idx] = True
                args[idx] = float(code[1:])

            # check if it's the first move in a sequence
            if self.newSequence:
                # don't worry about checking anything, just continue with next g-code line
                # after prepping variables for next loop
                self.init_sequence(flags, args, self.curXYZ, self.curE)

            else:
                # check feedrate versus previous move
                if flags[1]:
                    if args[1] != self.sequenceFeedrate:
                        # the commanded feedrate is different than the sequence feedrate,
                        # so we need to write out the G-code and start a new sequence with this move
                        result += self.finish_sequence(self.sequenceXYZ[-1], self.sequenceE[-1], self.sequenceFeedrate)
                        self.init_sequence(flags, args, self.curXYZ, self.curE)
                        continue

                # check extruder activity versus previous move.
                # note that I'm only checking consistency of direction of extruder motion (+/-/0)
                # theoretically, an increase or decrease in speed will mess this up, but I don't
                # expect incoming G code to do that. Something to fix later perhaps.
                if flags[5]:  # an E position is commanded
                    eDir = sign(args[5] - self.sequenceE[-1])
                else:
                    eDir = 0

                if eDir != self.sequenceExtruding:
                    # the extruder is starting, stopping, or changing direction, so we need
                    # to start a new sequence
                    result += self.finish_sequence(self.sequenceXYZ[-1], self.sequenceE[-1], self.sequenceFeedrate)
                    self.init_sequence(flags, args, self.curXYZ, self.curE)
                    continue

                # we've made it this far, so the feedrate and extruder behavior haven't changed.
                # so now we check the geometry of the path in XYZ - how much error would be
                # introduced if we eliminate this segment and just link it to the previous?

                # calculate the orthogonal distances between all intermediate points and the
                # "shortcut" line. see http://mathworld.wolfram.com/Point-LineDistance3-Dimensional.html

                next_xyz = copy.deepcopy(self.sequenceXYZ[-1])

                if flags[2]:
                    next_xyz.x = args[2]
                if flags[3]:
                    next_xyz.y = args[3]
                if flags[4]:
                    next_xyz.z = args[4]
                if flags[5]:
                    self.nextE = args[5]

                pos_1 = copy.deepcopy(self.curXYZ)
                pos_2 = copy.deepcopy(next_xyz)
                errors = []
                if pos_1 == pos_2:  # start and finish in same place
                    for pos_i in self.sequenceXYZ:
                        errors.append((pos_i - pos_1).mag())
                else:
                    sequence_length = (pos_2 - pos_1).mag()

                    for pos_i in self.sequenceXYZ:
                        err_1 = pos_i - pos_1
                        err_2 = pos_i - pos_2
                        errors.append(err_1.cross(err_2).mag() / sequence_length)

                error_large = any(e > error_threshold for e in errors)

                # make a new segment regardless of error if z-axis position change
                if error_large or (next_xyz.z != self.curXYZ.z):
                    # the error is too great, so we need to close out the previous sequence and start a new one
                    result += self.finish_sequence(self.sequenceXYZ[-1], self.sequenceE[-1],
                                                   self.sequenceFeedrate)
                    self.init_sequence(flags, args, self.curXYZ, self.curE)
                else:
                    # the errors are all below the threshold, so continue the sequence
                    self.sequenceXYZ.append(next_xyz.copy())
                    self.sequenceE.append(copy.deepcopy(self.nextE))

        # we're at the end of the file, so write out the final open sequence (if there is one)
        if not self.newSequence:
            result += self.finish_sequence(self.sequenceXYZ[-1], self.sequenceE[-1], self.sequenceFeedrate)

        return "\n".join(result)

