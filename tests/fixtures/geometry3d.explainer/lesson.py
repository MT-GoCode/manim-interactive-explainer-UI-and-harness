from manim import RIGHT, UL, Dot, FadeIn, Text, ThreeDAxes

from explainers import Lesson3D


class Geometry3D(Lesson3D):
    def construct(self):
        # Looking straight down z, zoom 2, focal distance 20, frame centre c = (0.25, 0): a point p at depth z is
        # drawn at 2·20/(20 − z)·(p − c) − c (Manim subtracts c when projecting and again when drawing; probed).
        self.set_camera_orientation(phi=0, zoom=2, frame_center=[0.25, 0, 0])
        self.cell("apart-in-the-world")
        # x 0.875 at z 0 → screen x 1.0, radius 0.16; x 0.5725 at z 10 → screen x 1.04, radius 0.32: apart in the
        # world, overlapping on screen; the first clears left by 1.16 − 0.72 = 0.44
        self.play(FadeIn(Dot(RIGHT * 0.875), Dot([0.5725, 0, 10])), run_time=0.1)
        self.cell("label-fixed-in-frame")
        self.clear()
        # the corner label is drawn where it is (zoom would put it far off frame); the axes are background
        label = Text("axes", font_size=40).to_corner(UL)
        self.add_fixed_in_frame_mobjects(label)
        self.play(FadeIn(ThreeDAxes(x_length=3, y_length=3, z_length=2), label), run_time=0.1)
