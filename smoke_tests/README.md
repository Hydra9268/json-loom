# 🧪 JSON-LOOM Smoke Tests

This folder contains **smoke tests** for `jsonloom.py`.  
They act like lightweight unit tests to verify that changes to the compiler
don’t break existing functionality.

## Running the tests

From this folder:

```bat
run_smoke_tests.bat
```

This will:

* Compile each `preprocessor_*.json` file
* Save compiled results under `results/`
* Log all output to `results/smoke_tests.log`
* Print a summary of passed/failed cases

---

## Adding a new smoke test

When you add a new feature to `jsonloom.py`, you should also add a new smoke test
to ensure it keeps working in the future.

1. **Create a preprocessor file** - 
   Add a new JSON file named `preprocessor_<feature>.json`
   (underscore style, to stay consistent).

2. **Update the presence check** - 
   In `run_smoke_tests.bat`, add the new file to the block that verifies inputs exist.

```bat
REM ---- presence checks ----
for %%I in (
  preprocessor_default_alias_id.json
  preprocessor_field_qualified.json
  preprocessor_whitespace_tolerance.json
  preprocessor_strict_projection.json
  preprocessor_object_map_imports.json
  preprocessor_missing_record.json
  preprocessor_unknown_alias.json
  preprocessor_circular_reference.json
  preprocessor_datalarge.json
  preprocessor_inventory_array.json
  [ADD HERE]
) do (
  if not exist "%%~I" (
    echo Missing input: %%~I >"%LOG%"
    type "%LOG%"
    popd
    exit /b 3
  )
)
```

3. **Update the test table** - 
   Add a new `T#` entry at the bottom of the test table in `run_smoke_tests.bat`:

   ```bat
   set "T12=my_feature|%LOOM% preprocessor_my_feature.json|0"
   ```

   * Replace `my_feature` with a descriptive label
   * Use `|0` if the test should succeed, or `|1` if it’s expected to fail

4. **Bump the loop counter** - 
   Update the `for /L %%N in (1,1,N)` line to include the new highest test number.

---

## Example

Adding a new `$ref` feature test:

1. Create `preprocessor_newref.json` in this folder
2. Add to presence check:

```bat
preprocessor_newref.json
```

3. Add to table:

```bat
set "T12=newref|%LOOM% preprocessor_newref.json|0"
```

4. Update loop:

```bat
for /L %%N in (1,1,12) do (
```

---

## Notes

* Keep test input files small and focused — they’re not full datasets, just minimal examples.
* Use underscores in filenames for consistency (`preprocessor_inventory_array.json`, not hyphens).
* Expected failures are just as important as successes — they prove error handling works.
