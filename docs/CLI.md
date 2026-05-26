# Commerce Data OOP CLI Utility Guide

The `data-oop` library comes with a built-in CLI utility for managing, validating, inspecting, and executing workflows in FalkorDB using the TBox (ontology) and ABox (data) models.

---

## 1. Installation & Running

### Running with `uv` (Local Development)

To run the CLI directly from the source directory:
```bash
# Display help
uv run data-oop --help

# Run a subcommand
uv run data-oop inspect
```

### Installing globally as a command

You can install the CLI globally on your machine using `uv tool`:
```bash
uv tool install .
```
This registers `data-oop` globally as an executable on your system path.

---

## 2. Global Database Options

You can specify database connections using command-line flags or environment variables:

| Argument | Environment Variable | Default Value | Description |
|---|---|---|---|
| `--host` | `FALKOR_HOST` | `localhost` | FalkorDB Host |
| `--port` | `FALKOR_PORT` | `6380` | FalkorDB Port |
| `--graph` | `FALKOR_GRAPH` | `data_oop` | Graph Name |
| `--username` | `FALKOR_USERNAME` | *None* | Authentication Username |
| `--password` | `FALKOR_PASSWORD` | *None* | Authentication Password |

Example using environment variables:
```bash
FALKOR_PORT=6380 FALKOR_GRAPH=prod_data data-oop inspect
```

---

## 3. Subcommands & Examples

### A. Inspect Schema (`inspect`)
Lists all Classes, Properties, Interfaces, Relationships, and Workflows defined in the DB.

```bash
data-oop inspect
```

### B. Load TBox Schema (`load-tbox`)
Parses a Python schema file, extracts a global `TBoxBuilder` (or `TBoxRepository` or `build_tbox()` function), and loads it into FalkorDB.

```bash
# Load schema (keeping existing nodes if possible)
data-oop load-tbox --file my_schema.py

# Re-create schema from scratch (wipes the graph first)
data-oop load-tbox --file my_schema.py --clear
```

#### Expected Schema File Format (`my_schema.py`)
```python
from data_oop import TBoxBuilder

builder = TBoxBuilder()
builder.class_("Department", description="Department info") \
    .property("name", datatype="string", required=True, unique=True) \
    .property("code", datatype="string", required=True, unique=True) \
    .end() \
    .class_("Project", description="Project info") \
    .property("title", datatype="string", required=True) \
    .property("budget", datatype="integer", required=False) \
    .end() \
    .relationship("rel_dept_runs_project", "RUNS", "Department", "Project")
```

### C. Run ABox Validation (`validate`)
Validates all ABox instances against the TBox schema currently loaded in FalkorDB. If there are validation errors, it prints details and exits with code `1`.

```bash
data-oop validate
```

### D. Clear ABox Data (`clear-abox`)
Deletes all ABox instances (domain-labeled nodes) while keeping the TBox schema definition and validation report structures intact.

```bash
# Interactive prompt
data-oop clear-abox

# Force clear without prompt (useful in scripts/CI)
data-oop clear-abox --yes
```

### E. Run Stored Workflows (`run-workflow`)
Runs a predefined workflow definition stored in the FalkorDB by name, substituting provided parameter values.

```bash
# Pass params as inline JSON string
data-oop run-workflow --name new_dept_project_workflow --params '{"project_title": "AI Platform Setup", "budget": 120000, "dept_uuid": "dept-it-01"}'

# Pass params from a JSON file
data-oop run-workflow --name new_dept_project_workflow --params-file params.json
```

---

## 4. Deployment & Distribution

### Packaging and Publishing to PyPI
The project is configured using `pyproject.toml` and built with `hatchling`.
To build and publish:
```bash
# Build wheel and source distributions
uv build

# Publish to PyPI
uv publish
```

### CI/CD Integration
In CI pipelines (like GitHub Actions), you can use the CLI to validate data consistency on changes:
```yaml
- name: Run Schema Validation
  env:
    FALKOR_HOST: ${{ secrets.DB_HOST }}
    FALKOR_PORT: 6380
    FALKOR_GRAPH: production
  run: |
    pip install data-oop
    data-oop validate
```
If any constraints are violated, `data-oop validate` will return non-zero exit status, failing the build pipeline automatically.
