import numpy as np
from manim import (DOWN, LEFT, ORIGIN, RIGHT, UL, UP, UR, YELLOW, Arrow, Axes, Brace, Circle, Dot, FadeIn, FadeOut,
                   ImageMobject, Line, MathTex, Matrix, NumberLine, NumberPlane, Square, SurroundingRectangle, Text, Underline,
                   VGroup, config)

from explainers import Lesson


class Geometry(Lesson):
    """One cell per case; each starts from an empty screen. Dots, squares and straight strokes give hand-checkable
    numbers (half a pixel s = 16 / 2160 / 2 = 0.0037)."""

    def show(self, slug, *mobs):
        self.cell(slug)
        self.clear()
        self.play(FadeIn(*mobs), run_time=0.1)

    def construct(self):
        # boxes [-0.08, 0.08]² and [0.02, 0.18]×[-0.08, 0.08]: shifts in (-0.06 + s, 0.26 - s) still overlap → -0.06
        self.show("dot-on-dot", Dot(ORIGIN), Dot(RIGHT * 0.1))
        self.show("dots-touch-by-under-half-a-pixel", Dot(ORIGIN), Dot(RIGHT * 0.158))
        self.show("text-on-text", Text("alpha", font_size=40), Text("beta", font_size=40).shift(RIGHT * 0.3))
        self.show("text-on-text-moved-as-told", Text("alpha", font_size=40).shift(UP * 0.44),
                  Text("beta", font_size=40).shift(RIGHT * 0.3))
        self.show("text-on-an-arrow", Arrow(LEFT * 3, RIGHT * 3, buff=0), Text("crosses", font_size=32))
        self.show("dot-on-an-arrow", Arrow(LEFT * 3, RIGHT * 3, buff=0), Dot(UP * 0.03))
        self.show("hidden-in-a-group", VGroup(Dot(ORIGIN), Dot(RIGHT * 0.1)))
        # squares of side 1: an edge at 8.5 or 4.5 against the frame's 8 and 4
        self.show("off-frame-right", Square(1).shift(RIGHT * 8))
        self.show("off-frame-left", Square(1).shift(LEFT * 8))
        self.show("off-frame-top", Square(1).shift(UP * 4))
        self.show("off-frame-fill", Square(1, stroke_width=0, fill_opacity=1).shift(DOWN * 4))
        self.show("off-frame-image", ImageMobject(np.full((8, 8, 4), 200, np.uint8)).set(height=1).shift(RIGHT * 8))
        self.show("under-half-a-pixel-past-the-edge", Square(1).move_to([config.frame_width / 2 - 0.5 + 0.003, 0, 0]))
        self.show("small-text", Text("tiny", font_size=28))
        self.show("small-latex", MathTex("x", font_size=36), Matrix([[1, 2], [3, 4]]).scale(0.5).shift(DOWN * 2))
        self.cell("leftover-transient")
        self.clear()
        self.play(FadeIn(self.transient(Circle())), run_time=0.1)
        self.cell("leftover-transient-group")
        self.clear()
        self.play(FadeIn(self.transient(VGroup(Circle(), Square(0.5)))), run_time=0.1)

        arrow = Arrow(LEFT * 3, RIGHT * 3, buff=0)
        self.show("attached", arrow, self.attach(Text("on it", font_size=32), arrow))
        pair = VGroup(Line(LEFT * 3, RIGHT * 3), Square(0.5).shift(DOWN * 2))
        self.show("attached-to-a-group", pair, self.attach(Text("on it", font_size=32), pair))
        grid = Matrix([[1, 2], [3, 4]])
        self.show("attached-to-a-part", grid,
                  self.attach(Text("4", font_size=32), grid.get_entries()[3]).move_to(grid.get_entries()[3]))
        shaft = Arrow(LEFT * 3, RIGHT * 3, buff=0)
        label = self.attach(Text("a", font_size=32), shaft)
        self.show("attached-and-copied", shaft, label, label.copy().shift(RIGHT * 1.5))
        self.show("punctuation-at-the-minimum", Text("a, b. c; d!", font_size=32),
                  MathTex(r"x_i, y.", font_size=40).shift(DOWN * 1.5))
        self.show("text-on-a-plane", NumberPlane(), Text("grid", font_size=48))
        self.cell("transient-gone")
        self.clear()
        cursor = self.transient(Circle())
        self.play(FadeIn(cursor), run_time=0.1)
        self.play(FadeOut(cursor), run_time=0.1)
        above = Line(LEFT * 3, RIGHT * 3)  # exactly horizontal: its chords' y-direction is 0, not float noise
        self.show("label-beside-a-line", above, Text("above", font_size=32).next_to(above, UP))

        # Realistic scenes (the rule's probe, at the minimum sizes) and staples: no message.
        X = Matrix([[1, 2, 3, 4], [5, 6, 7, 8], [9, 1, 2, 3]]).scale(0.85).to_edge(LEFT, buff=0.8).shift(DOWN)
        W = Matrix([[1, 0], [0, 1], [2, 2], [3, 1]]).scale(0.85).next_to(X, UP, buff=0.3).shift(RIGHT * 2.5)
        Y = Matrix([[0, 0], [0, 0], [0, 0]]).scale(0.85).next_to(X, RIGHT, buff=1.2).align_to(X, UP)
        self.show("matmul-with-cursors", X, W, Y, MathTex("X").next_to(X, LEFT), MathTex("W").next_to(W, LEFT),
                  MathTex("XW").next_to(Y, RIGHT), SurroundingRectangle(X.get_rows()[1], color=YELLOW),
                  SurroundingRectangle(W.get_columns()[0], color=YELLOW))
        plane = NumberPlane()
        v, w = Arrow(plane.c2p(0, 0), plane.c2p(3, 2), buff=0), Arrow(plane.c2p(0, 0), plane.c2p(-2, 3), buff=0)
        self.show("plane-with-vectors-and-points", plane, v, MathTex(r"\vec v").next_to(v.get_end(), UR, buff=0.1),
                  w, MathTex(r"\vec w").next_to(w.get_end(), UL, buff=0.1),
                  VGroup(*[Dot(plane.c2p(x, y)) for x, y in [(1, -1), (2, -2), (-3, -1), (3, 2)]]))
        slope = Arrow(LEFT * 4 + DOWN * 2, RIGHT * 2 + UP * 2)
        box = Square(1.2).set_fill(YELLOW, 0.6).shift(RIGHT * 4.5 + DOWN * 2)
        value = Text("0.48", font_size=32).move_to(box)
        self.show("arrow-label-number-in-a-box-highlight", slope,
                  Text("gradient", font_size=32).next_to(slope.get_center(), UL, buff=0.15), box, value,
                  SurroundingRectangle(value, buff=0.1))
        width = Square(2).shift(UP)
        brace = Brace(width, DOWN)
        word = Text("word", font_size=40).shift(DOWN * 2.5 + LEFT * 3)
        root = MathTex(r"\sqrt{x^2 + 1}").shift(DOWN * 2.5 + RIGHT * 2)
        self.show("brace-underline-root", width, brace, brace.get_text("width"), word, Underline(word), root,
                  Text("root", font_size=32).next_to(root, RIGHT))
        ax = Axes(x_range=[0, 3], y_range=[0, 9], x_length=5, y_length=4)
        self.show("point-on-a-curve", ax, ax.plot(lambda x: x ** 2), Dot(ax.c2p(2, 4)))
        self.show("graph-edge-with-nodes", Line(LEFT * 2, RIGHT * 2), Dot(LEFT * 2), Dot(RIGHT * 2))
        # a unit with glyphs AND strokes: its move must keep its own line off the other's glyphs too
        self.show("number-line-under-text", NumberLine(x_range=[-4, 4, 1], length=8, include_numbers=True, font_size=40),
                  Text("here", font_size=40).move_to([1, -0.3, 0]))
        self.show("number-line-moved-as-told",
                  NumberLine(x_range=[-4, 4, 1], length=8, include_numbers=True, font_size=40).shift(UP * 0.30),
                  Text("here", font_size=40).move_to([1, -0.3, 0]))
