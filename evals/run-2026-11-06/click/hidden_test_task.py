import pytest

import click


@pytest.mark.parametrize(
    ("param", "expected"),
    [
        (click.Option(["-t", "--times"]), "--times"),
        (click.Option(["--times", "-t"]), "--times"),
        (click.Option(["-c", "--count", "number"]), "--count"),
        (click.Option(["--color/--no-color"]), "--color"),
        (click.Option(["-v"], hidden=True), "-v"),
        (click.Argument(["filename"]), "FILENAME"),
        (click.Argument(["filename"], required=False, nargs=-1), "FILENAME"),
        (click.Argument(["filename"], metavar="<file>"), "<file>"),
    ],
)
def test_param_info_dict_has_spec(param, expected):
    info = param.to_info_dict()
    assert info["spec"] == expected
    assert info["spec"] == param.spec
    assert info["name"] == param.name


def test_info_dict_spec_follows_subclass_override():
    class Custom(click.Option):
        @property
        def spec(self) -> str:
            return "--custom"

    assert Custom(["--times"]).to_info_dict()["spec"] == "--custom"


def test_info_dict_spec_does_not_touch_human_readable_name(recwarn):
    click.Option(["--times"]).to_info_dict()
    click.Argument(["filename"]).to_info_dict()
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def test_context_info_dict_params_have_spec():
    @click.command()
    @click.argument("recipe")
    @click.option("-g", "--gluten-free/--no-gluten-free")
    def bake(recipe, gluten_free):
        pass

    ctx = click.Context(bake)
    params = {p["name"]: p for p in ctx.to_info_dict()["command"]["params"]}
    assert params["recipe"]["spec"] == "RECIPE"
    assert params["gluten_free"]["spec"] == "--gluten-free"
    assert params["_click_default_help"]["spec"] == "--help"
