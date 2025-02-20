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
from typing import Literal

AstType = Literal['classes', 'functions', 'imports', 'methods']
"""Type alias for AST types to extract from code files."""


class KnowledgeGenerator:
    """Generate code knowledge for AI agent."""

    def __init__(
        self,
        input_dir: str,
        output_dir: str = 'temp',
        *,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        content_docstring: bool = True,
        content_internal: bool = True,
        content_types: set[AstType] | None = None,
        max_chars: int | None = None,
        max_files: int | None = None,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(os.getcwd()) / output_dir
        self.include_patterns = include_patterns or ['*.py']
        self.exclude_patterns = exclude_patterns or [
            '*__pycache__*', '*test*', '*.pyc', '*.git*'
        ]
        self.content_docstring = content_docstring
        self.content_internal = content_internal
        self.content_types = content_types or {
            'classes', 'functions', 'imports', 'methods'
        }
        self.max_chars = max_chars
        self.max_files = max_files
        self.processed_files = 0

    def build_knowledge(self) -> dict[str, str]:
        """Build code knowledge from input directory files."""
        knowledge = {}

        # Walk through input directory Python files
        for file in self.input_dir.rglob('*.py'):
            if self.max_files and self.processed_files >= self.max_files:
                print(f"Reached maximum file limit ({self.max_files})")
                break
            if not self._check_path(file):
                continue

            relative_path = file.relative_to(self.input_dir)
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    try:
                        processed_content = self._parse_content(content)
                        if processed_content:
                            knowledge[str(relative_path)] = processed_content
                            self.processed_files += 1
                    except SyntaxError:
                        print(f"Warning: Could not parse {file}")
            except Exception as error:
                print(f"Error processing {file}: {error}")

        return knowledge

    def build_tree_view(self) -> dict:
        """Build tree view from input directory files."""

        def walk_tree(path: Path) -> dict:
            tree = {}
            for item in path.iterdir():
                if item.is_file():
                    if not self._check_path(item):
                        continue
                    tree[item.name] = None
                else:
                    tree_node = walk_tree(item)
                    if not tree_node:
                        continue
                    tree[item.name] = tree_node
            return tree

        return walk_tree(self.input_dir)

    def export(self):
        """Export generated knowledge and tree to JSON files."""
        self.output_dir.mkdir(exist_ok=True)

        knowledge = self.build_knowledge()
        with open(self.output_dir / 'agent_knowledge.json', 'w') as f:
            json.dump(knowledge, f, indent=2)

        tree = self.build_tree_view()
        with open(self.output_dir / 'agent_tree.json', 'w') as f:
            json.dump(tree, f, indent=2)

        print(f"\nGenerated files in {self.output_dir}:")
        print(f"- agent_knowledge.json")
        print(f"- agent_tree.json")
        print(f"\nProcessed {self.processed_files} files")

    def _check_name(self, name: str) -> bool:
        """Whether to include a name based on internal content setting."""
        return self.content_internal or not name.startswith('_')

    def _check_path(self, path: Path) -> bool:
        """Whether to include a path based on include/exclude patterns."""
        return (
            not any(path.match(p) for p in self.exclude_patterns)
            and any(path.match(p) for p in self.include_patterns)
        )

    def _extract_docstring(self, node: ast.AST) -> str | None:
        """Extract docstring from AST node."""
        docstring = ast.get_docstring(node)
        if self.max_chars and docstring and len(docstring) > self.max_chars:
            docstring = docstring[:self.max_chars] + '...'
        return docstring

    def _extract_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature from AST node."""
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

    def _parse_content(self, content: str) -> dict:
        """Parse code content and extract relevant parts."""
        code = ast.parse(content)
        parts = {}

        if self.content_docstring:
            parts['docstring'] = self._extract_docstring(code)

        if 'classes' in self.content_types:
            parts['classes'] = {}
            for node in ast.walk(code):
                if not isinstance(node, ast.ClassDef):
                    continue
                if not self._check_name(node.name):
                    continue
                parts['classes'][node.name] = cls_info = {}
                if self.content_docstring:
                    cls_info['docstring'] = self._extract_docstring(node)
                if 'methods' in self.content_types:
                    cls_info['methods'] = {}
                    for item in node.body:
                        if not isinstance(item, ast.FunctionDef):
                            continue
                        if not self._check_name(item.name):
                            continue
                        cls_info['methods'][item.name] = info = {}
                        if self.content_docstring:
                            info['docstring'] = self._extract_docstring(item)
                        info['signature'] = self._extract_signature(item)

        if 'functions' in self.content_types:
            parts['functions'] = {}
            for node in ast.walk(code):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if not self._check_name(node.name):
                    continue
                parts['functions'][node.name] = fn_info = {}
                if self.content_docstring:
                    fn_info['docstring'] = self._extract_docstring(node)
                fn_info['signature'] = self._extract_signature(node)

        if 'imports' in self.content_types:
            parts['imports'] = []
            for node in ast.walk(code):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                parts['imports'].append(ast.unparse(node))

        return parts


def main():
    parser = argparse.ArgumentParser(
        description='Generate repo documentation resources for AI agent'
    )

    parser.add_argument(
        '--input-dir', '-i',
        help='Input directory',
        default='src/plateforme',
    )
    parser.add_argument(
        '--output-dir', '-o',
        help='Output directory for generated resources',
        default='temp',
    )
    parser.add_argument(
        '--include',
        nargs='*',
        help='Patterns to include (e.g., "*.py")',
    )
    parser.add_argument(
        '--exclude',
        nargs='*',
        help='Patterns to exclude (e.g., "*test*")',
    )
    parser.add_argument(
        '--types',
        nargs='+',
        choices=['classes', 'functions', 'imports', 'methods'],
        default=['classes', 'functions', 'imports', 'methods'],
        help='Types of content to extract',
    )
    parser.add_argument(
        '--no-docstring',
        action='store_true',
        help='Only include public members (exclude prefixed with underscore)',
    )
    parser.add_argument(
        '--no-internal',
        action='store_true',
        help='Only include public members (exclude prefixed with underscore)',
    )
    parser.add_argument(
        '--max-chars',
        type=int,
        help='Maximum number of characters allowed in docstrings',
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process',
    )

    args = parser.parse_args()

    generator = KnowledgeGenerator(
        args.input_dir,
        args.output_dir,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
        content_docstring=not args.no_docstring,
        content_internal=not args.no_internal,
        content_types=set(args.types),
        max_chars=args.max_chars,
        max_files=args.max_files,
    )

    generator.export()


if __name__ == '__main__':
    main()
