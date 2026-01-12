from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os


def generate_document(content_dict: Dict[str, Any], template_path: str) -> str:
    """
    Render a briefing document using a Jinja2 markdown template.
    """
    template_dir = os.path.dirname(template_path)
    template_file = os.path.basename(template_path)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=()),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(template_file)
    return template.render(**content_dict)
