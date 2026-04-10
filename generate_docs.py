import json
import sys

from fastapi.openapi.utils import get_openapi
from app.main import app

def generate_markdown():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    
    with open("docs/API_REFERENCE.md", "w") as f:
        f.write(f"# {app.title} API Reference (v{app.version})\n\n")
        f.write(f"{app.description}\n\n")
        
        paths = openapi_schema.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                tags = ", ".join(details.get("tags", []))
                f.write(f"## {method.upper()} {path}\n")
                f.write(f"**Tags:** {tags}\n\n")
                f.write(f"{details.get('summary', '')}\n\n")
                
                f.write("### Parameters\n")
                parameters = details.get("parameters", [])
                if parameters:
                    for param in parameters:
                        name = param.get("name", "")
                        in_loc = param.get("in", "")
                        req = "Required" if param.get("required") else "Optional"
                        f.write(f"- `{name}` ({in_loc}): {req}\n")
                else:
                    f.write("*None*\n")
                
                f.write("\n---\n\n")
                
generate_markdown()
