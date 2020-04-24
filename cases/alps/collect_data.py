# coding: utf-8

import re
import os
import time
from ngta import current_context
from calterah.util import get_positions_from_str
from bench import TestBench

import logging
logger = logging.getLogger(__name__)


def collect_akbk_for_angles(angles, nframe, interval=None, output_dir=None):
    if isinstance(angles, str):
        angles = get_positions_from_str(angles)

    context = current_context()
    testbench: TestBench = context.testbench
    text = ''
    for pos in angles:
        testbench.rot.goto(**pos)
        if interval is not None:
            time.sleep(interval)
        frames = testbench.dut.scan(nframe)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output = os.path.join(output_dir, "X{}Y{}.txt".format(pos["x"], pos["y"]))
            with open(output, "w") as f:
                f.write(frames.raw)
        text += frames.raw
    logger.debug("data: \n%s", text)
    return text


def _check_range_and_index(text, rng_index):
    lines = text.strip().split('\n')
    for line in lines[1:]:
        # check rng_index should always be same during test.
        match = re.search(r'rng_index (\d+)', line)
        new_rng_index = match.group(1)
        if rng_index is None:
            rng_index = new_rng_index
        else:
            if rng_index != new_rng_index:
                raise AssertionError("rng_index is not match")

        # check range should not be 0.00
        no_range = re.search(r'range 0.00', line)
        if no_range:
            raise AssertionError("range should not be 0.00")
    return rng_index


def collect_ant_calib_for_angles(angles, range_min=None, range_max=None, ignore_error=False, interval=None, output=None):
    if isinstance(angles, str):
        angles = get_positions_from_str(angles)

    context = current_context()
    testbench: TestBench = context.testbench

    repeat = 1

    # call ant_calib to get raw data
    text = ''
    rng_index = None
    for pos in angles:
        testbench.rot.goto(**pos)
        if interval is not None:
            time.sleep(interval)
        for i in range(repeat):
            c = 'ant_calib X{}Y{}'.format(pos["x"], pos["y"])
            if range_min:
                c += " {}".format(range_min)
            if range_max:
                c += " {}".format(range_max)
            resp = testbench.dut.command(c, timeout=2)
            if not ignore_error:
                rng_index = _check_range_and_index(resp, rng_index)

            if i == 1:
                resp = "\n".join(resp.split('\n')[1:])

            if output:
                with open(output, "a") as f:
                    f.write(resp)
                    f.flush()
            text += resp
    logger.debug("data: \n%s", text)
    return text


def collect_akbk_for_one_emulated_target(rcs, rng, vel, ang, nframe, output=None):
    context = current_context()
    testbench: TestBench = context.testbench
    target = testbench.simulators.acquire_target()
    target.set_rcs(rcs)
    target.set_range(rng)
    target.set_speed(vel)
    target.set_angle(ang)
    frames = testbench.dut.scan(nframe)

    if output:
        os.makedirs(os.path.dirname(output), exist_ok=True)

        filename = os.path.join(output.format(rcs=rcs, rng=rng, vel=vel, ang=ang))
        with open(filename, "w") as f:
            f.write(frames.raw)
    return frames


def collect_data_adc():
    raise NotImplementedError
