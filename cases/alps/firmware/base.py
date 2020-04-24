# coding: utf-8

from typing import Union
from ngta import TestCase, route, test
from calterah.adapters.alps import Frame, DeviceAdapter, TrackMode, get_standard_tolerance

from ..bench import TestBench

ToleranceType = Union[int, float, list, tuple]
TrackModeType = Union[TrackMode, str]


def get_trace_mode_str(mode: TrackModeType):
    mode = mode.value if isinstance(mode, TrackMode) else mode
    return mode.lower()


class BaseTestCase(TestCase):
    testbench: TestBench

    def setup(self):
        if self.testbench.app.is_process_running():
            self.testbench.app.close()

        if not self.testbench.dut.is_open:
            self.testbench.dut.open()

    def _check_frame(self, frame: Frame, mode: TrackModeType, *,
                     num_of_tracked_targets: int = None,
                     rng, rng_tolerance: ToleranceType = 0,
                     vel, vel_tolerance: ToleranceType = 0,
                     ang=None, ang_tolerance: ToleranceType = 0):
        mode = get_trace_mode_str(mode)
        tracked_targets = getattr(frame, mode)
        if num_of_tracked_targets is not None:
            message = 'frame {} should only tracked one object.'.format(frame.idx)
            self.assert_that(tracked_targets, message).is_length(num_of_tracked_targets)

        rng_tolerance = get_standard_tolerance(rng_tolerance)
        vel_tolerance = get_standard_tolerance(vel_tolerance)
        ang_tolerance = get_standard_tolerance(ang_tolerance)

        found = frame.find_target(mode,
                                  rng=rng, rng_tolerance=rng_tolerance,
                                  vel=vel, vel_tolerance=vel_tolerance,
                                  ang=ang, ang_tolerance=ang_tolerance)
        message = 'Frame {} should find target with: rng {}{}, vel {}{}, ang {}{}'.format(
            frame.idx, rng, rng_tolerance, vel, vel_tolerance, ang, ang_tolerance)
        self.assert_that(found, message).is_not_none()

    def _check_target_in_frames(self, frames, mode: TrackModeType, occurrence: int = None, **kwargs):
        with self.soft_assertions() as errors:
            for frame in frames:
                self._check_frame(frame, mode, **kwargs)

            if occurrence:
                actual_occurrence = len(frames) - len(errors)
                message = 'Target should be occurred greater than or equal to {}'.format(occurrence)
                self.assert_that(actual_occurrence, message).is_greater_than_or_equal_to(occurrence)

    def _check_target_bk_in_frames(self, frames, **kwargs):
        self._check_target_in_frames(frames, 'bk', **kwargs)

    def _check_target_ak_in_frames(self, frames, **kwargs):
        self._check_target_in_frames(frames, 'ak', **kwargs)
