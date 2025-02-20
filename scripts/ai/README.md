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
| `--input-dir`, `-i` | Source code directory path | `src/plateforme` | `-i /path/to/code` |
| `--output-dir`, `-o` | Output directory for generated files | `temp` | `-o docs` |
| `--include` | File patterns to include | `["*.py"]` | `--include "*.py" "*.pyx"` |
| `--exclude` | File patterns to exclude | `["*__pycache__*", "*test*", "*.pyc", "*.git*"]` | `--exclude "*test*" "*build*"` |
| `--types` | Types of content to extract | _All (see bellow)_ | `--types classes` |
| `--no-docstring` | Remove docstrings from output | `False` | `--no-docstring` |
| `--no-internal` | Filter out internal members | `False` | `--no-internal` |
| `--max-chars` | Maximum number of characters in docstrings | `None` | `--max-chars 1000` |
| `--max-files` | Maximum number of files to process | `None` | `--max-files 100` |

### Content types

Available content types for extraction:
- `classes`: Class definitions and their docstrings
- `functions`: Function definitions and signatures
- `imports`: Import statements
- `methods`: Class methods and their signatures

### Output files

The tool generates two JSON files in the output directory:

2. `agent_knowledge.json`: Extracted code content knowledge
1. `agent_tree.json`: Input directory file structure

### Examples

#### Basic usage

```bash
python scripts/ai/knowledge.py
```

#### Extract public only knowledge with limited docstring characters

```bash
python scripts/ai/knowledge.py --no-internal --max-chars 500
```

#### Extract specific knowledge types and patterns with limited files

```bash
python scripts/ai/knowledge.py \
    --output-dir docs \
    --include "*.py" "*.pyx" \
    --exclude "*test*" "*build*" \
    --types docstrings functions \
    --max-files 50
```

### Output format

#### `agent_knowledge.json`

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

## Agent instructions

```markdown
Python documentation agent
---

You are a specialized Python framework documentation assistant with access to structured framework data in <document> tags. The data includes:

1. "agent_tree.json": Repository file structure

2. "agent_knowledge.json": Analyzed Python code including:
  - Module docstrings
  - Class and methods definitions
  - Function signatures
  - Import dependenciesr

As a documentation expert, you will create Markdown documentation pages optimized for Material for MkDocs. For each documentation request, you will:

1. Write professional technical content:
  - Create clear, focused documentation in standard Markdown
  - Use proper Material for MkDocs Markdown features when beneficial
  - Include appropriate code examples and explanations
  - Maintain consistent formal and technical writing style

2. Consider full context:
  - Review all provided code context for accuracy
  - Reference related components where relevant
  - Ensure technical completeness and correctness
  - Write with awareness of the broader framework

Each response must be a single, complete Markdown document that fits the specific documentation request while leveraging the available code context information.

ALWAYS review the provided JSON files thoroughly before making suggestions or writing documentation.
```
