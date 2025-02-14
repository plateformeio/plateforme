#!/usr/bin/env python3

# plateforme.scripts.ai.knowledge
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

import argparse
import ast
import json
import os
from pathlib import Path
from typing import Set


class KnowledgeGenerator:
    def __init__(
        self,
        input_dir: str,
        output_dir: str = "temp",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        content_types: Set[str] | None = None,
        max_files: int | None = None,
        public_only: bool = False
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(os.getcwd()) / output_dir
        self.include_patterns = include_patterns or ["*.py"]
        self.exclude_patterns = exclude_patterns or [
            "*test*", "*__pycache__*", "*.pyc", "*.git*"
        ]
        self.content_types = content_types or {
            "docstrings", "classes", "functions", "imports"
        }
        self.max_files = max_files
        self.processed_files = 0
        self.public_only = public_only

    def _is_public(self, name: str) -> bool:
        """Check if a name is public (not starting with _ or __)."""
        return not (name.startswith('_') or name.startswith('__'))

    def generate_tree_structure(self) -> dict:
        """Generate a tree structure of the repository."""
        tree = {}

        def build_tree(path: Path, current_dict: dict) -> None:
            for item in path.iterdir():
                if self._should_exclude(item):
                    continue

                if item.is_file():
                    current_dict[item.name] = None
                else:
                    current_dict[item.name] = {}
                    build_tree(item, current_dict[item.name])

        build_tree(self.input_dir, tree)
        return tree

    def extract_code_content(self) -> dict[str, str]:
        """Extract content from Python files."""
        content_map = {}

        for py_file in self.input_dir.rglob("*.py"):
            if self.max_files and self.processed_files >= self.max_files:
                print(f"Reached maximum file limit ({self.max_files})")
                break

            if self._should_exclude(py_file):
                continue

            relative_path = py_file.relative_to(self.input_dir)
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try:
                        tree = ast.parse(content)
                        cleaned_content = self._parse_content(tree, content)
                        # Only include requested content types
                        filtered_content = {
                            k: v for k, v in cleaned_content.items()
                            if k in self.content_types
                        }
                        # Only add if there's content after filtering
                        if filtered_content:
                            content_map[str(relative_path)] = filtered_content
                            self.processed_files += 1
                    except SyntaxError:
                        print(f"Warning: Could not parse {py_file}")
            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        return content_map

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded based on patterns."""
        return (
            any(path.match(p) for p in self.exclude_patterns)
            and not any(path.match(p) for p in self.include_patterns)
        )

    def _parse_content(self, tree: ast.AST, original_content: str) -> dict:
        """Parse content from the code."""
        parts = {}

        if "docstrings" in self.content_types:
            parts['docstring'] = ast.get_docstring(tree)

        if "classes" in self.content_types:
            parts['classes'] = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if self.public_only and not self._is_public(node.name):
                    continue
                class_info = {'docstring': ast.get_docstring(node)}
                if "methods" in self.content_types:
                    class_info['methods'] = {}
                    for item in node.body:
                        if not isinstance(item, ast.FunctionDef):
                            continue
                        if self.public_only and not self._is_public(item.name):
                            continue
                        class_info['methods'][item.name] = {
                            'docstring': ast.get_docstring(item),
                            'signature': self._get_function_signature(item)
                        }
                parts['classes'][node.name] = class_info

        if "functions" in self.content_types:
            parts['functions'] = {}
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if self.public_only and not self._is_public(node.name):
                    continue
                if node.name != '__init__':
                    parts['functions'][node.name] = {
                        'docstring': ast.get_docstring(node),
                        'signature': self._get_function_signature(node)
                    }

        if "imports" in self.content_types:
            parts['imports'] = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    parts['imports'].append(ast.unparse(node))

        return parts

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        signature = f"def {node.name}({', '.join(args)})"
        if node.returns:
            signature += f" -> {ast.unparse(node.returns)}"
        return signature

    def generate_resources(self):
        """Generate all documentation resources."""
        self.output_dir.mkdir(exist_ok=True)

        tree = self.generate_tree_structure()
        with open(self.output_dir / "agent_tree.json", 'w') as f:
            json.dump(tree, f, indent=2)

        content = self.extract_code_content()
        with open(self.output_dir / "agent_content.json", 'w') as f:
            json.dump(content, f, indent=2)

        print(f"\nGenerated files in {self.output_dir}:")
        print(f"- agent_tree.json")
        print(f"- agent_content.json")
        print(f"\nProcessed {self.processed_files} files")
        if self.max_files:
            print(f"Max files limit: {self.max_files}")
        print(f"Content types included: {', '.join(self.content_types)}")
        if self.public_only:
            print("Including public members only (no _ or __)")


def main():
    parser = argparse.ArgumentParser(
        description="Generate repo documentation resources for AI agent"
    )

    parser.add_argument(
        "--input_dir",
        help="Input directory",
        default="src/plateforme",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for generated resources",
        default="temp",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="Patterns to include (e.g., '*.py')",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        help="Patterns to exclude (e.g., '*test*')",
    )
    parser.add_argument(
        "--content-types",
        nargs="+",
        choices=["docstrings", "classes", "functions", "imports", "methods"],
        default=["docstrings", "classes", "functions", "imports", "methods"],
        help="Types of content to extract",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum number of files to process",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Only include public members (exclude _ and __ prefixed)",
    )

    args = parser.parse_args()

    generator = KnowledgeGenerator(
        args.input_dir,
        args.output_dir,
        args.include,
        args.exclude,
        set(args.content_types),
        args.max_files,
        args.public_only
    )
    generator.generate_resources()


if __name__ == "__main__":
    main()
