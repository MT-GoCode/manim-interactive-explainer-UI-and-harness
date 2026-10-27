from manim import (DOWN, LEFT, ORIGIN, RIGHT, UP, Arrow, Circle, Dot, FadeIn, FadeOut, Line, MathTex, Matrix,
                   NumberPlane, Square, Text, VGroup, config)

from explainers import Lesson


class Geometry(Lesson):
    """One cell per case; each starts from an empty screen. Dots and straight strokes give hand-checkable numbers."""

    def show(self, slug, *mobs):
        self.cell(slug)
        self.clear()
        self.play(FadeIn(*mobs), run_time=0.1)

    def construct(self):
        # glyph boxes [-0.08, 0.08]² and [0.02, 0.18]×[-0.08, 0.08]: clears left by 0.06
        self.show("dot-on-dot", Dot(ORIGIN), Dot(RIGHT * 0.1))
        self.show("text-on-text", Text("alpha", font_size=40), Text("beta", font_size=40).shift(RIGHT * 0.3))
        # dot box y in [-0.05, 0.11], the shaft at y = 0: clears up by 0.05
        self.show("dot-on-arrow-shaft", Arrow(LEFT * 3, RIGHT * 3, buff=0), Dot(UP * 0.03))
        self.show("hidden-in-a-group", VGroup(Dot(ORIGIN), Dot(RIGHT * 0.1)))
        # stroke reaches x = 7.5; the frame's right edge is 7.11
        self.show("off-frame-stroke", Square(1).shift(RIGHT * 7))
        # fill only, bottom edge at -4.5; the frame's bottom is -4
        self.show("off-frame-fill", Square(1, stroke_width=0, fill_opacity=1).shift(DOWN * 4))
        self.show("small-text", Text("tiny", font_size=28))
        self.show("small-latex", MathTex("x", font_size=36), Matrix([[1, 2], [3, 4]]).scale(0.5).shift(DOWN * 2))
        self.cell("leftover-transient")
        self.clear()
        self.play(FadeIn(self.transient(Circle())), run_time=0.1)

        arrow = Arrow(LEFT * 3, RIGHT * 3, buff=0)
        self.show("attached", arrow, self.attach(Dot(UP * 0.03), arrow))
        pair = VGroup(Line(LEFT * 3, RIGHT * 3), Square(0.5).shift(DOWN * 2))
        self.show("attached-to-a-group", pair, self.attach(Text("on it", font_size=32), pair))
        self.show("punctuation-at-the-minimum", Text("a, b. c; d!", font_size=32), MathTex(r"x_i, y.", font_size=40).shift(DOWN * 1.5))
        self.show("text-on-a-plane", NumberPlane(), Text("grid", font_size=48))
        self.cell("transient-gone")
        self.clear()
        cursor = self.transient(Circle())
        self.play(FadeIn(cursor), run_time=0.1)
        self.play(FadeOut(cursor), run_time=0.1)
        above = Arrow(LEFT * 3, RIGHT * 3, buff=0)
        self.show("label-beside-an-arrow", above, Text("above", font_size=32).next_to(above, UP))
        # 0.003 past the right edge: under half a pixel (14.22 / 1920 / 2 = 0.0037), so nothing is drawn outside
        self.show("under-half-a-pixel-past-the-edge", Square(1).move_to([config.frame_width / 2 - 0.5 + 0.003, 0, 0]))
