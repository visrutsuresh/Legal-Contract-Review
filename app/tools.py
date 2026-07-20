TOOLS = {}  # name -> function


def tool(fn):
    # Register a function so an agent can call it by name
    TOOLS[fn.__name__] = fn
    return fn


def run_tool(name: str, args: dict) -> str:
    # Dial a tool by name with its args; return the result as a text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR:unknown tool {name!r}"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"
