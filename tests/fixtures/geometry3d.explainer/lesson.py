from manim import RIGHT, UL, Dot, FadeIn, Text, ThreeDAxes

from explainers import Lesson3D


class Geometry3D(Lesson3D):
    def construct(self):
        # Looking straight down z, zoom 2, focal distance 20: a point at depth z is drawn at 2·20/(20 − z) its x, y.
        self.set_camera_orientation(phi=0, zoom=2)
        self.cell("apart-in-the-world")
        # x 0.5 at z 0 → screen x 1.0, radius 0.16; x 0.26 at z 10 → screen x 1.04, radius 0.32: apart in the world,
        # overlapping on screen; the first clears left by 1.16 − 0.72 = 0.44
        self.play(FadeIn(Dot(RIGHT * 0.5), Dot([0.26, 0, 10])), run_time=0.1)
        self.cell("label-fixed-in-frame")
        self.clear()
        # the corner label is drawn where it is (zoom would put it far off frame); the axes are background
        label = Text("axes", font_size=40).to_corner(UL)
        self.add_fixed_in_frame_mobjects(label)
        self.play(FadeIn(ThreeDAxes(x_length=3, y_length=3, z_length=2), label), run_time=0.1)
