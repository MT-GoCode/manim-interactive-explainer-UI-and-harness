import numpy as np
from manim import *

from explainers import Lesson

N = 30
values = np.round(np.linspace(-1, 1, N) ** 3, 3)


class Long(Lesson):
    def construct(self):
        row = VGroup(*[Square(0.35).set_fill(BLUE, 0.5) for _ in range(10)]).arrange(RIGHT, buff=0.1)
        spinner = Square(0.3, color=YELLOW).to_corner(UR)
        spinner.add_updater(lambda m, dt: m.rotate(0.8 * dt))  # runs during every animation, chunked or not
        jitter = np.random.uniform(-0.2, 0.2, N)  # one draw per lesson: every process must draw the same numbers
        for k in range(N):
            self.cell(f"step-{k:02d}")
            if k == 0:
                self.play(FadeIn(row), FadeIn(spinner), run_time=1.0)
            v = DecimalNumber(values[k], num_decimal_places=3, font_size=40).to_edge(DOWN).shift(RIGHT * jitter[k])
            self.play(row[k % 10].animate.set_fill(RED if values[k] > 0 else GREEN, 0.9), FadeIn(v),
                      run_time=0.6 + 0.4 * (k % 3))
            self.play(FadeOut(v), run_time=0.3)
            self.wait(0.1)  # two waits per cell take the lesson past Manim's 100-file partial pruning limit
            self.wait(0.1)
            if k == 9:
                self.play(FadeOut(spinner), run_time=0.3)
                self.remove(spinner)
