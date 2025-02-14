# Agent

A tool for generating documentation resources from Python code repositories. It extracts docstrings, classes, functions, and imports to create structured JSON output files.

## Agent knowledge generation

### Usage

```bash
python scripts/ai/knowledge.py [options]
```

### Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `--input-dir` | Source code directory path | `src/plateforme` | `--input-dir=/path/to/code` |
| `--output-dir` | Output directory for generated files | `temp` | `--output-dir=docs` |
| `--include` | File patterns to include | `["*.py"]` | `--include "*.py" "*.pyx"` |
| `--exclude` | File patterns to exclude | `["*test*", "*__pycache__*", "*.pyc", "*.git*"]` | `--exclude "*test*" "*build*"` |
| `--content-types` | Types of content to extract | All types | `--content-types docstrings classes` |
| `--max-files` | Maximum number of files to process | None | `--max-files 100` |
| `--public-only` | Extract only public members | `False` | `--public-only` |

### Content types

Available content types for extraction:
- `docstrings`: Module and class level documentation
- `classes`: Class definitions and their docstrings
- `functions`: Function definitions and signatures
- `imports`: Import statements
- `methods`: Class methods and their signatures

### Output files

The tool generates two JSON files in the output directory:

1. `agent_tree.json`: Repository structure
2. `agent_content.json`: Extracted code content

### Examples

#### Basic usage

```bash
python scripts/ai/knowledge.py
```

#### Extract public only custom content types

```bash
python scripts/ai/knowledge.py --content-types docstrings classes functions methods --public-only
```

#### Extract custom content types and patterns with limited files

```bash
python scripts/ai/knowledge.py \
    --content-types docstrings functions \
    --include "*.py" "*.pyx" \
    --exclude "*test*" "*build*" \
    --output-dir docs \
    --max-files 50
```

### Output format

#### `agent_tree.json`

```json
{
  "mymodule": {
    "core.py": null,
    "utils": {
      "helpers.py": null
    }
  }
}
```

#### `agent_content.json`

```json
{
  "mymodule/core.py": {
    "docstring": "Module documentation",
    "classes": {
      "MyClass": {
        "docstring": "Class documentation",
        "methods": {
          "my_method": {
            "docstring": "Method documentation",
            "signature": "def my_method(self, arg: str) -> bool"
          }
        }
      }
    }
  }
}
```

## Agent instructions

```markdown
Python documentation agent
---

You are a specialized Python framework documentation assistant with access to structured framework data in <document> tags. The data includes:

1. agent_tree.json: Repository file structure
2. agent_content.json: Analyzed Python code including:
  - Module docstrings
  - Class definitions and docstrings
  - Function signatures with types
  - Import dependencies

Please help me create comprehensive framework documentation by:
- Analyzing the provided code structure and content
- Suggesting documentation organization
- Writing clear API references, tutorials, and guides
- Creating examples and code snippets
- Maintaining consistency throughout the documentation

Remember to:
- Consider the entire codebase context when documenting components
- Explain design patterns and architectural decisions
- Follow Python documentation best practices
- Make documentation accessible to users of different skill levels

Always review the provided JSON files thoroughly before making suggestions or writing documentation.
```
