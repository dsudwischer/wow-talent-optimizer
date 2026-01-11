from jinja2 import Environment
from pydantic import BaseModel

_OUTPUT_PART = """
# Saving Report Data
#html={{html_file_path}}
json2={{json_file_path}}
"""


class RenderArgs(BaseModel):
    name: str
    level: int
    race: str
    class_talent_string: str
    spec_talent_string: str
    hero_talent_string: str


def get_html_file_path(output_name: str) -> str:
    return f"./simc/output/{output_name}.html"


def get_json_file_path(output_name: str) -> str:
    return f"./simc/output/{output_name}.json"


class SimcTemplate:
    def __init__(self, template_string: str):
        self._template = Environment().from_string(template_string + _OUTPUT_PART)

    def render(self, render_args: RenderArgs, output_name: str) -> str:
        render_kwargs = render_args.model_dump(mode="json")
        render_kwargs["json_file_path"] = get_json_file_path(output_name)
        render_kwargs["html_file_path"] = get_html_file_path(output_name)
        return self._template.render(**render_kwargs)
