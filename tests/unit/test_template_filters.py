"""Tests for custom Jinja2 template filters."""

from regulatory_agent_kit.templates.engine import (
    TemplateEngine,
    _basename_filter,
    _camel_case_filter,
    _dirname_filter,
    _pascal_case_filter,
    _snake_case_filter,
)


class TestBasenameFilter:
    def test_simple_path(self) -> None:
        assert _basename_filter("src/models/user.py") == "user.py"

    def test_just_filename(self) -> None:
        assert _basename_filter("file.txt") == "file.txt"

    def test_trailing_slash(self) -> None:
        assert _basename_filter("src/models/") == "models"

    def test_empty_string(self) -> None:
        assert _basename_filter("") == ""


class TestDirnameFilter:
    def test_simple_path(self) -> None:
        assert _dirname_filter("src/models/user.py") == "src/models"

    def test_just_filename(self) -> None:
        assert _dirname_filter("file.txt") == "."

    def test_nested(self) -> None:
        assert _dirname_filter("/a/b/c/d.py") == "/a/b/c"


class TestSnakeCaseFilter:
    def test_camel_case(self) -> None:
        assert _snake_case_filter("camelCase") == "camel_case"

    def test_pascal_case(self) -> None:
        assert _snake_case_filter("PascalCase") == "pascal_case"

    def test_already_snake(self) -> None:
        assert _snake_case_filter("already_snake") == "already_snake"

    def test_with_spaces(self) -> None:
        assert _snake_case_filter("some string") == "some_string"

    def test_with_hyphens(self) -> None:
        assert _snake_case_filter("kebab-case") == "kebab_case"

    def test_acronyms(self) -> None:
        assert _snake_case_filter("HTTPResponse") == "http_response"

    def test_empty(self) -> None:
        assert _snake_case_filter("") == ""


class TestCamelCaseFilter:
    def test_snake_case(self) -> None:
        assert _camel_case_filter("snake_case") == "snakeCase"

    def test_with_hyphens(self) -> None:
        assert _camel_case_filter("kebab-case") == "kebabCase"

    def test_with_spaces(self) -> None:
        assert _camel_case_filter("some string") == "someString"

    def test_already_camel(self) -> None:
        assert _camel_case_filter("camelCase") == "camelcase"

    def test_single_word(self) -> None:
        assert _camel_case_filter("word") == "word"

    def test_empty(self) -> None:
        assert _camel_case_filter("") == ""


class TestPascalCaseFilter:
    def test_snake_case(self) -> None:
        assert _pascal_case_filter("snake_case") == "SnakeCase"

    def test_with_hyphens(self) -> None:
        assert _pascal_case_filter("kebab-case") == "KebabCase"

    def test_with_spaces(self) -> None:
        assert _pascal_case_filter("some string") == "SomeString"

    def test_single_word(self) -> None:
        assert _pascal_case_filter("word") == "Word"

    def test_empty(self) -> None:
        assert _pascal_case_filter("") == ""


class TestFiltersRegistered:
    def test_all_filters_available(self) -> None:
        engine = TemplateEngine()
        for name in ("basename", "dirname", "snake_case", "camel_case", "pascal_case"):
            assert name in engine._env.filters

    def test_filter_in_template(self) -> None:
        engine = TemplateEngine()
        result = engine.render_string("{{ name | snake_case }}", {"name": "MyClass"})
        assert result == "my_class"

    def test_basename_in_template(self) -> None:
        engine = TemplateEngine()
        result = engine.render_string("{{ path | basename }}", {"path": "src/foo/bar.py"})
        assert result == "bar.py"

    def test_chained_filters(self) -> None:
        engine = TemplateEngine()
        result = engine.render_string(
            "{{ path | basename | pascal_case }}",
            {"path": "src/my_module.py"},
        )
        assert result == "MyModule.py"
