__all__ = ["Lesson", "Lesson3D", "LessonError"]


def __getattr__(name):  # lazily: importing this package must not import manim (a child changes directory first)
    if name in __all__:
        from explainers import lesson
        return getattr(lesson, name)
    raise AttributeError(name)
