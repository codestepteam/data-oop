# data-oop CLI Usage Guide

The `data-oop` command-line utility provides tools to manage, inspect, validate, and run workflows in FalkorDB.

---

## 1. Installation & Execution

### Running locally (using `uv`)

No installation required. Run directly from the project directory:

```bash
uv run data-oop --help
```

### Global Installation

Install the tool globally on your system path:

```bash
uv tool install .
```

After installation, the command `data-oop` will be globally available.

---

## 2. Configuration (Environment Variables & Flags)

Connection parameters can be set via command-line flags or environment variables:

| Flag         | Environment Variable | Default     | Description           |
| ------------ | -------------------- | ----------- | --------------------- |
| `--host`     | `FALKOR_HOST`        | `localhost` | FalkorDB host address |
| `--port`     | `FALKOR_PORT`        | `6380`      | FalkorDB port         |
| `--graph`    | `FALKOR_GRAPH`       | `data_oop`  | Database graph name   |
| `--username` | `FALKOR_USERNAME`    | _None_      | FalkorDB username     |
| `--password` | `FALKOR_PASSWORD`    | _None_      | FalkorDB password     |

Example with environment variables:

```bash
FALKOR_HOST="macmini" FALKOR_PORT=6380 data-oop inspect
```

---

## 3. Command Reference

### A. `inspect`

Displays TBox definition details (Classes, Properties, Relationships) and list of stored Workflows.

```bash
data-oop inspect
```

### B. `validate`

Validates ABox node instances against the current TBox schema. Prints list of issues and exits with code `1` if validation errors exist.

```bash
# Run validation
data-oop validate

# Run validation with a custom run ID
data-oop validate --run-id custom-validation-run
```

### C. `clear-abox`

Wipes all ABox instance nodes (domain data) from the graph, keeping TBox and validation schemas intact.

```bash
# Interactive prompt
data-oop clear-abox

# Force clear without interactive prompt (useful for automation)
data-oop clear-abox --yes
```

### D. `run-workflow`

Executes a stored workflow by name, using provided parameters.

```bash
# Run with inline JSON parameters
data-oop run-workflow --name add_new_product --params '{"product_name": "Keyboard", "price": 45000}'

# Run with parameters loaded from a JSON file
data-oop run-workflow --name add_new_product --params-file params.json
```

---

## 4. CI/CD Integration

To automatically validate data integrity in a CI pipeline (e.g., GitHub Actions):

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

If validation fails, the command exits with code `1`, causing the pipeline stage to fail.
