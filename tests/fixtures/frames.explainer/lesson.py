from pathlib import Path

import numpy as np
from manim import *

from explainers import Lesson

HERE = Path(__file__).parent


def square(fill=BLUE, stroke=4.0):
    return Square(1.5).set_fill(fill, 1).set_stroke(WHITE, stroke)


class Frames(Lesson):
    """Pairs of cells (<case>-a, <case>-b); each cell starts and ends on an empty screen, so a pair's recorded frames
    are equal exactly when what the two cells draw is."""

    def construct(self):
        self.cell("same-a")
        self.play(FadeIn(Square(2).shift(RIGHT)), run_time=0.2)
        self.clear()
        self.cell("same-b")
        self.play(FadeIn(Square(2).move_to(RIGHT)), run_time=0.2)
        self.clear()

        self.cell("rate-a")
        self.add(square())
        self.wait(0.2)
        self.clear()
        self.cell("rate-b")
        self.add(square())
        self.wait(0.2167)
        self.clear()

        self.cell("fill-a")
        self.play(FadeIn(square(RED)), run_time=0.2)
        self.clear()
        self.cell("fill-b")
        self.play(FadeIn(square(GREEN)), run_time=0.2)
        self.clear()

        self.cell("stroke-a")
        self.play(FadeIn(square(stroke=4)), run_time=0.2)
        self.clear()
        self.cell("stroke-b")
        self.play(FadeIn(square(stroke=8)), run_time=0.2)
        self.clear()

        self.cell("order-a")
        self.add(square(RED, 0).shift(0.5 * LEFT), square(GREEN, 0).shift(0.5 * RIGHT))
        self.wait(0.2)
        self.clear()
        self.cell("order-b")
        self.add(square(GREEN, 0).shift(0.5 * RIGHT), square(RED, 0).shift(0.5 * LEFT))
        self.wait(0.2)
        self.clear()

        self.cell("gradient-a")
        self.play(FadeIn(Square(2).set_fill([RED, BLUE], 1)), run_time=0.2)
        self.clear()
        self.cell("gradient-b")
        self.play(FadeIn(Square(2).set_fill([RED, GREEN], 1)), run_time=0.2)
        self.clear()

        self.cell("static-a")
        self.add(square(RED).shift(2 * LEFT))
        self.play(Dot().animate.shift(RIGHT), run_time=0.2)
        self.clear()
        self.cell("static-b")
        self.add(square(GREEN).shift(2 * LEFT))
        self.play(Dot().animate.shift(RIGHT), run_time=0.2)
        self.clear()

        self.cell("image-a")
        self.play(FadeIn(ImageMobject(np.full((8, 8, 3), 200, np.uint8)).scale(20)), run_time=0.2)
        self.clear()
        self.cell("image-b")
        self.play(FadeIn(ImageMobject(np.full((8, 8, 3), 100, np.uint8)).scale(20)), run_time=0.2)
        self.clear()

        self.cell("points-a")
        self.play(FadeIn(PMobject(stroke_width=20).add_points(np.array([[0, 0, 0], [1, 0, 0]]), color=RED)), run_time=0.2)
        self.clear()
        self.cell("points-b")
        self.play(FadeIn(PMobject(stroke_width=20).add_points(np.array([[0, 0, 0], [1, 0, 0]]), color=GREEN)), run_time=0.2)
        self.clear()

        self.cell("hold-a")
        self.add(square())
        self.wait(0.2)
        self.clear()
        self.cell("hold-b")
        self.add(square())
        self.wait(0.4)
        self.clear()

        live = lambda: Dot().add_updater(lambda m: m)  # drawn every frame: no frozen frames, no repeats
        self.cell("halves-a")
        self.add(live())
        self.wait(0.4)
        self.clear()
        self.cell("halves-b")
        self.add(live())
        self.wait(0.2)
        self.wait(0.2)
        self.clear()

        self.cell("background-a")
        self.camera.background_color = DARK_BLUE
        self.play(FadeIn(square()), run_time=0.2)
        self.clear()
        self.cell("background-b")
        self.camera.background_color = DARK_BROWN
        self.play(FadeIn(square()), run_time=0.2)
        self.clear()
        self.camera.background_color = BLACK

        self.cell("backimage-a")
        self.play(FadeIn(Square(2).set_fill(WHITE, 1).color_using_background_image(str(HERE / "warm.png"))),
                  run_time=0.2)
        self.clear()
        self.cell("backimage-b")
        self.play(FadeIn(Square(2).set_fill(WHITE, 1).color_using_background_image(str(HERE / "cool.png"))),
                  run_time=0.2)
        self.clear()
