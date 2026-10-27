from manim import *

from explainers import Lesson
from helpers import P, Z  # L:import-helpers

p_top = float(P.max())
n_tokens = len(Z)


def label(text):
    return Text(text, font_size=40)  # L:label-helper (the innermost lesson.py line: a lesson-local helper reports its own line)


class Softmax(Lesson):
    def construct(self):
        self.cell("scores")
        z = VGroup(*[DecimalNumber(v, num_decimal_places=2, font_size=40) for v in Z]).arrange(RIGHT, buff=0.5)  # L:z
        self.play(Write(z), run_time=1.0)
        self.cell("exp")
        title = label("e to the z").to_edge(UP)  # L:title
        self.play(FadeIn(title), run_time=0.5)
        self.wait(0.25)
        self.cell("sum")
        s = MathTex(r"\sum_j e^{z_j}", font_size=48).next_to(z, DOWN, buff=0.8)  # L:sum
        self.play(Write(s), run_time=0.75)
        self.cell("divide")
        frac = MathTex(r"p_i = \frac{e^{z_i}}{\sum_j e^{z_j}}", font_size=48).to_edge(DOWN)  # L:frac
        self.play(ReplacementTransform(s.copy(), frac), run_time=1.25)  # L:frac-copy
        self.cell("probs")
        note = Text("probabilities", font_size=64).scale(0.75).to_corner(UL)  # L:note
        self.add(note)
        self.play(FadeOut(title), run_time=0.5)
        self.cell("top")
        box = SurroundingRectangle(z[3], color=YELLOW)  # L:box
        twin = note.copy().to_corner(UR)  # L:twin
        self.play(Create(box), FadeIn(twin), run_time=0.5)
        grid = Matrix([[1, 2], [3, 4]]).scale(0.9).to_corner(DR)  # L:matrix
        self.add(grid)
        self.wait(0.1234)
