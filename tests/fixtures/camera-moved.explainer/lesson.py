from manim import DEGREES, Dot, FadeIn

from explainers import Lesson3D


class Moved(Lesson3D):
    def construct(self):
        self.set_camera_orientation(phi=60 * DEGREES)
        self.cell("still")
        self.play(FadeIn(Dot()), run_time=0.1)
        self.cell("turns")
        self.move_camera(theta=30 * DEGREES, run_time=0.1)
