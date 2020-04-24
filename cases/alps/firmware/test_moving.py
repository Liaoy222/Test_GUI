# coding: utf-8

from .base import OneTargetTestCase, TwoTargetTestCase


class T1(OneTargetTestCase):
    def test_target_change_lane(self, src_angle=-5, dst_angle=5, rcs=20, rng=20, vel=18):
        self.target.set_angle(src_angle)
        self.target.move(rcs, rng, vel, dst_angle, 5)
        frames = self.dut.scan(60)
        self.target.stop()


class T2(TwoTargetTestCase):
    def test_two_target_change_lane(self,
                                    rcs=20,
                                    target1_src_angle=-10,
                                    target1_dst_angle=0,
                                    target1_rng=30,
                                    target1_vel=30,
                                    target2_src_angle=10,
                                    target2_dst_angle=0,
                                    target2_rng=30,
                                    target2_vel=30
                                    ):
        self.target1.set_angle(target1_src_angle)
        self.target2.set_angle(target2_src_angle)

        self.target1.move(rcs, target1_rng, target1_vel, target1_dst_angle, 5)
        self.target2.move(rcs, target2_rng, target2_vel, target2_dst_angle, 5)

        frames = self.dut.scan(60)
        self.target.stop()
