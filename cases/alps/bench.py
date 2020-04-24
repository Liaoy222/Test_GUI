# coding: utf-8

import os
import atexit
from typing import List, Optional
from ngta import TestBench as BaseTestBench, TestCase
from ngta.agent import TestBench as AgentTestBench
from calterah.simulator.keycom import find_simulators, get_default_setups_by_freq, DEFAULT_RTS_LIB_DIR, Simulators
from pywinauto import Application

from calterah.adapters import alps
from calterah import arduino
from calterah.instruments.analyzer import AnalyzerFactory

import logging
logger = logging.getLogger(__name__)


class MeasureTestBench(BaseTestBench):
    def __init__(self,
                 dut_comport=None, dut_baudrate=None,
                 dut_fw_override=False, dut_fw_src_dir=None, dut_fw_make_options=None,
                 rot_comport=None, analyzer_host=None,
                 src_comport=None, src_baudrate=None
                 ):
        super().__init__("MeasureTestBench", type='alps', exclusive=True)

        if not dut_comport:
            dut_comport = alps.find_available_comport()
        dut_baudrate = dut_baudrate or 3000000
        self.dut = alps.DeviceAdapter(
            comport=dut_comport, baudrate=dut_baudrate,
            fw_override=dut_fw_override, fw_src_dir=dut_fw_src_dir, fw_make_options=dut_fw_make_options
        )

        if src_comport:
            src_baudrate = src_baudrate or 3000000
            self.src = alps.DeviceAdapter(comport=src_comport, baudrate=src_baudrate)
        else:
            self.src = None

        if not rot_comport:
            rot_comport = arduino.find_available_comport()
        self.rot = arduino.Rotary(rot_comport) if rot_comport else None

        if analyzer_host:
            if "::" in analyzer_host:
                ana_kwargs = {"resource": analyzer_host}
            else:
                ana_kwargs = {"host": analyzer_host}
            self.analyzer = AnalyzerFactory.new_analyzer(**ana_kwargs)
        else:
            self.analyzer = None
        atexit.register(self.on_testrunner_stopped, None)

    def on_testrunner_started(self, event):
        self.dut.open()
        if self.src:
            self.src.open()

        if self.rot and not self.rot.is_open():
            self.rot.open()
            self.rot.reset()

        if self.analyzer:
            self.analyzer.open()

    def on_testrunner_stopped(self, event):
        if self.analyzer:
            self.analyzer.close()

        if self.rot and self.rot.is_open():
            self.rot.reset()
            self.rot.close()

        if self.src:
            self.src.close()

        self.dut.close()


ALPS_GUI_EXE_PATH = r"C:\Calterah\DevHelper_alps.exe"


class AppWrapper(Application):
    def __init__(self, exe_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exe_path = exe_path
        self.is_closed = True
        self.main_page = None
        self.uart_page = None
        self.track_fps = None

    def restart(self):
        self.close()
        self.open()

    def open(self):
        from .gui.pages import MainPage, UartPage

        logger.debug("Start application: %s", self.exe_path)
        self.start(self.exe_path, work_dir=os.path.dirname(self.exe_path))
        self.is_closed = False
        self.main_page = MainPage.from_app(self)
        self.uart_page = UartPage.from_app(self)

    def close(self):
        if not self.is_closed:
            logger.debug("Close application: %s", self.exe_path)
            self.main_page.window.close()
            self.is_closed = True

    @property
    def is_open(self):
        return not self.is_closed


class TestBench(AgentTestBench):
    simulators: Simulators
    dut: Optional[alps.DeviceAdapter]
    rot: Optional[arduino.Rotary]
    app: Optional[AppWrapper]

    def __init__(self,
                 name: str,
                 alps_gui_exe_path: str = ALPS_GUI_EXE_PATH,
                 rts_lib_dir: str = DEFAULT_RTS_LIB_DIR,
                 rts_setups: List[dict] = None,
                 routes: List[str] = None,
                 group: str = None):
        super().__init__(name=name, type='alps', exclusive=True, routes=routes, group=group)
        self.simulators = Simulators()
        self.alps_gui_exe_name = os.path.basename(alps_gui_exe_path)
        self.alps_gui_exe_path = alps_gui_exe_path
        self.rts_setups = rts_setups
        self.rts_lib_dir = rts_lib_dir

        # for support running testcase in agent, assign following vars in method on_testrunner_started.
        self.dut = None
        self.app = None
        self.rot = None

    def __str__(self):
        return "<{}(name:{})>".format(self.__class__.__name__, self.name)

    def on_testrunner_started(self, event):
        self.simulators = find_simulators(self.rts_lib_dir)
        self.dut = alps.DeviceAdapter(alps.find_available_comport(), fw_override=False)
        self.app = AppWrapper(self.alps_gui_exe_path, backend="uia")

        comport = arduino.find_available_comport()
        if arduino.find_available_comport():
            self.rot = arduino.Rotary(comport)

        os.system('taskkill /F /T /IM {}'.format(self.alps_gui_exe_name))

        self.dut.try_open()
        fmcw_startfreq = self.dut.get_sensor_cfg("fmcw_startfreq")
        fmcw_bandwidth = self.dut.get_sensor_cfg("fmcw_bandwidth")
        center_freq = fmcw_startfreq + fmcw_bandwidth * 1e-3 / 2
        track_fps = self.dut.get_sensor_cfg("track_fps")

        # if not self.rts_setups:
        #     self.rts_setups = get_default_setups_by_freq(center_freq)

        for index, simulator in enumerate(self.simulators):
            simulator.open()
            try:
                simulator.setup(**self.rts_setups[index])
            except IndexError:
                logger.warning("Don't find rts setup for %s", simulator)

        self.app.track_fps = track_fps

        if self.rot:
            self.rot.open()
            self.rot.reset()

    def on_testrunner_stopped(self, event):
        if self.rot:
            self.rot.reset()
            self.rot.close()

        for simulator in self.simulators:
            simulator.close()

        if self.app.is_process_running():
            self.app.close()

        if self.dut.is_open:
            self.dut.close()

    def on_testcase_started(self, event):
        testcase: TestCase = event.target
        if testcase.path.startswith("alps.gui"):
            if self.dut.is_open:
                self.dut.close()

            if not self.app.is_open:
                self.app.open()
        else:
            if self.app.is_open:
                self.app.close()

            if not self.dut.is_open:
                self.dut.open()

    def as_dict(self):
        d = super().as_dict()
        d['rts_setups'] = self.rts_setups
        d['rts_lib_dir'] = self.rts_lib_dir
        d['routes'] = self.routes
        return d

    @classmethod
    def from_dict(cls, d) -> 'TestBench':
        return cls(d["name"], rts_lib_dir=d["rts_lib_dir"],  rts_setups=d["rts_setups"], routes=d["routes"])
