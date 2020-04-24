# coding: utf-8

from typing import NoReturn
from ngta import current_context
from ngta.events import TestEventHandler, TestCaseFailedEvent


class FailFreezeInterceptor(TestEventHandler):
    def on_testcase_failed(self, event: TestCaseFailedEvent) -> NoReturn:
        context = current_context()
        context.testbench.dut.close()
        input('[Press ENTER to continue:]')
