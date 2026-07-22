import os
import re
from pathlib import Path

tests_dir = Path(
    "/Users/kalaimaranbalasothy/GitHub Projects/BioPro-flow-cytometry/tests"
)
local_modules = ["ui", "analysis", "tutorials"]

changes_made = 0
for root, _, files in os.walk(tests_dir):
    for file in files:
        if not file.endswith(".py"):
            continue
        py_file = Path(root) / file

        content = py_file.read_text(encoding="utf-8")
        lines = content.split("\n")
        modified = False

        for i, line in enumerate(lines):
            for mod in local_modules:
                # from analysis.foo import ...
                pattern_from = r"^(\s*)from\s+" + mod + r"\b"
                if re.search(pattern_from, line):
                    lines[i] = re.sub(
                        pattern_from,
                        r"\1from biopro.plugins.flow_cytometry." + mod,
                        line,
                    )
                    modified = True

                # import analysis.foo
                pattern_import = r"^(\s*)import\s+" + mod + r"\b"
                if re.search(pattern_import, line):
                    lines[i] = re.sub(
                        pattern_import,
                        r"\1import biopro.plugins.flow_cytometry." + mod,
                        line,
                    )
                    modified = True

        if modified:
            py_file.write_text("\n".join(lines), encoding="utf-8")
            changes_made += 1
            print(f"Updated {py_file.relative_to(tests_dir)}")

print(f"Total test files updated: {changes_made}")
