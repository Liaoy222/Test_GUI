# coding: utf-8

import re
import time
from typing import List
from pprint import pprint
from ngta import TestCase, TestEventHandler, current_context
from coupling.dict import AttrDict
from bench import MeasureTestBench
from calterah.constants import LOCH_HTTP_URL

import numpy as np
import requests


class BaseTestCase(TestCase):
    pass


class AnalyzerTestCase(BaseTestCase):
    testbench: MeasureTestBench

    def setup(self):
        self.testbench.analyzer.preset()
        self.testbench.analyzer.mixer_signal_id()
        self.testbench.analyzer.trace('MAXHold')
        self.testbench.analyzer.peak_table(threshold=self.parameters.threshold)
        self.testbench.analyzer.command(':SENS:BAND:RES 100000')   # RBW: sense bandwidth resolution:

        min_freq = min(self.parameters.frequencies) - 1
        max_freq = max(self.parameters.frequencies) + 1
        self.testbench.analyzer.frequency('{} GHz'.format(min_freq), '{} GHz'.format(max_freq))

        self.testbench.dut.command('bb_interframe single')
        self.testbench.dut.command('scan start 1')
        self.record.extras["chip_name"] = self.testbench.dut.chip_name

    def _enable_tx(self, tx, dev=None):
        index = tx["index"]
        phase = tx["phase"]
        dev = dev or self.testbench.dut
        dev.command('radio_tx on %s' % index)
        if phase:
            dev.command('radio_txphase {} {}'.format(index, phase))

    def _check_all_tx_phase(self, tx_config: List[dict], dev=None):
        dev = dev or self.testbench.dut
        s = dev.command('radio_txphase')
        founds = re.findall(r'CH(\d):(\d{1,3})', s)
        actual_phases = dict(founds)
        with self.soft_assertions():
            for tx in tx_config:
                index = tx["index"]
                phase = tx["phase"]
                if phase:
                    actual_phase = int(actual_phases[str(index)])
                    self.assert_that(phase).is_equal_to(actual_phase)

    def _check_one_tx_phase(self, tx):
        s = self.testbench.dut.command('radio_txphase')
        founds = re.findall(r'CH(\d{1}):(\d{1,3})', s)
        actual_phases = dict(founds)
        index = tx["index"]
        phase = tx["phase"]
        if phase:
            self.assert_that(phase).is_equal_to(actual_phases[index])

    def _measure_peak(self, freq, wait=3, unlocked_retry: int = 3, unlocked_interval=1):
        record = AttrDict()
        if self.testbench.dut.chip_rev == 'MP':
            cmd = 'radio_single_tone {}'
        else:
            cmd = 'radio_fmcw_hold {}'

        for _ in range(unlocked_retry):
            resp = self.testbench.dut.command(cmd.format(freq))
            self.testbench.analyzer.trace('write')
            self.testbench.analyzer.trace('MAXHold')

            record.is_unlocked = 'unlocked' in resp
            if record.is_unlocked:
                time.sleep(unlocked_interval)
            else:
                break

        time.sleep(wait)        # get peak list from analyzer after waiting.
        record.hold = freq
        record.peak, record.dbm = self._fetch_peak()
        return record

    def _fetch_peak(self):
        raw_peak_list = self.testbench.analyzer.get_peak_list()
        if len(raw_peak_list) == 1:
            peak, dbm = raw_peak_list[0]
        elif len(raw_peak_list) == 0:
            peak = None
            dbm = None
        else:
            self.warn_('peak list should not greater than 1.')
            dbm_list = list(np.array(raw_peak_list)[:, 1])
            index = dbm_list.index(max(dbm_list))
            peak, dbm = raw_peak_list[index]
        return peak, dbm


class TestRecordHandler(TestEventHandler):
    def __init__(self, board_name, board_rev, sn, comment, tester, test_type):
        super().__init__()
        self.board_name = board_name
        self.board_rev = board_rev
        self.sn = sn
        self.comment = comment
        self.tester = tester
        self.test_type = test_type

    def on_testcase_stopped(self, event) -> None:
        testcase = event.target
        record = testcase.record

        if record.status in (record.Status.PASSED, record.Status.WARNING):
            data = {
                'chip_name': record.extras["chip_name"],
                'chip_rev': current_context().testbench.dut.chip_rev,
                'board_name': self.board_name,
                'board_rev': self.board_rev,
                'sn': self.sn,
                'comment': self.comment,
                'tester': self.tester,
                'data': record.extras['data'],
                # 'command': " ".join(sys.argv)
            }

            pprint(data)
            resp = requests.post('{}/loch/api/histories/{}'.format(LOCH_HTTP_URL, self.test_type), json=data)
            if resp.ok:
                print('*** Access {}/history/{}/{} to view result'.format(
                    self.test_type, LOCH_HTTP_URL, resp.json()['id'])
                )
            else:
                raise Exception('Upload data to server failed.')


def get_index_and_phase_from_tx(tx):
    index = tx[0]
    phase = None
    try:
        phase = tx[1]
    except IndexError:
        pass
    return index, phase


def get_tx_config_from_arg(arg):
    tx_config = []
    for tx in arg:
        index, phase = get_index_and_phase_from_tx(tx)
        tx_config.append(dict(index=index, phase=phase))
    return tx_config
