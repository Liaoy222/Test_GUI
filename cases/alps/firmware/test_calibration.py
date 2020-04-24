# coding: utf-8

import re
import tempfile
import numpy as np
from calterah.util import xrange_by_str
from radar_plot_routines import ant_calib
from coupling.dict import AttrDict
from ngta import TestCase, tag, test
from ..test_calibration import CalibrationTestCase, Direction, Axis
from ..bench import TestBench

import logging
logger = logging.getLogger(__name__)

H_TX_GROUPS = [1, 2, 3, 4]
V_TX_GROUPS = [1, 2, 3, 4]


class Test(TestCase):
    testbench: TestBench

    @tag('sanity')
    @test('test calibration result is closed to last release.')
    def test_calibration(self):
        parameters = dict(
            h=Direction(Axis.H,
                        angles=xrange_by_str('-10:10:1'),
                        config={'tx_groups': '1 2 3 4', 'vel_nfft': int(256/max(H_TX_GROUPS))}),

            v=Direction(Axis.V,
                        angles=xrange_by_str('-6:6:0.5'),
                        config={'tx_groups': '1 2 3 4', 'vel_nfft': int(256/max(V_TX_GROUPS))}),
            sensor_cfg={},
        )
        test = CalibrationTestCase('test', parameters=parameters)
        test.run()

        record = test.record
        h_text = record.extras['h_text']
        v_text = record.extras['v_text']

        h_temp = tempfile.mktemp()
        with open(h_temp, 'w') as f:
            f.write(h_text)

        v_temp = tempfile.mktemp()
        with open(v_temp, 'w') as f:
            f.write(v_text)

        args = AttrDict(
            h_filename=h_temp,
            v_filename=v_temp,
            h_tx_groups=H_TX_GROUPS,
            v_tx_groups=V_TX_GROUPS,
            h_ants_groups=None,
            v_ants_groups=None,
            output_dir=None,
            adjust_angle=None,
        )

        resp = ant_calib.main(args)
        logger.debug(resp)

        pos_line = None
        com_line = None
        for line in resp.split('\n'):
            if 'ant_prog pos' in line:
                pos_line = line

            if 'ant_prog comp' in line:
                com_line = line

        actual_pos = [float(v) for v in re.findall(r'(-?\d+\.\d+)', pos_line)]
        actual_com = [float(v) for v in re.findall(r'(-?\d+\.\d+)', com_line)]

        pos_resp = self.testbench.dut.command('ant_prog pos')
        com_resp = self.testbench.dut.command('ant_prog com')
        expect_pos = [float(v) for v in re.findall(r'(-?\d+\.\d+)', pos_resp)]
        expect_com = [float(v) for v in re.findall(r'(-?\d+\.\d+)', com_resp)]

        logger.debug('actual pos: %s', actual_pos)
        logger.debug('expect pos: %s', expect_pos)
        pos_is_closed = np.allclose(actual_pos, expect_pos, atol=0.05)

        logger.debug('actual comp: %s', actual_com)
        logger.debug('expect comp: %s', expect_com)
        com_is_closed = np.allclose(actual_com, expect_com, atol=0.05)

        self.assert_that(pos_is_closed).is_true()
        self.assert_that(com_is_closed).is_true()
