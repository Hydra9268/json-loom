<div align="center">
  <img src="https://hydra9268.github.io/json-loom/assets/json-loom-logo-2.2.png"/>
  <h1>JSON-LOOM</h1>
  <h3>Weave relational JSON into denormalized documents.<br>A preprocessor for document databases.</h3>
</div>

## 📑 Table of Contents

- [🎯 Description](#-description)
- [✨ Features](#-features)
- [📦 Example](#-example)
- [⚙️ Usage](#-usage)
- [▶ Next Steps: Using Compiled Documents](#-next-steps-using-compiled-documents)
- [💾 Working with BSON and Binary Data](#-working-with-bson-and-binary-data)
  - [🖼️ Binary data](#-binary-data)
  - [🧭 Design Decision](#-design-decision)
- [📜 Syntax](#-syntax)
  - [🔗 `$imports`](#-imports)
    - [🗝️ `Note on IDs`](#-note-on-ids)
  - [🧩 `$ref`](#-ref)
  - [✂️ `$alias`](#-pick)
- [📥 Installation](#-installation)
- [📂 Recommended File Structure](#-recommended-file-structure)

---

## 🎯 Description

JSON-LOOM is a lightweight preprocessor that lets you author **normalized JSON** (similar to 
relational tables) and compile it into **flat, document-friendly JSON** optimized for 
document databases (e.g., MongoDB, CouchDB, Firestore). Think of it as **Sass for JSON**:

- Write once  
- Keep it DRY  
- Compile to ready-to-use output

---

## ✨ Features

- `$imports` for relational JSON or BSON sources
- `$ref` syntax with flexible spacing (`product:1`, `product : 1`)
- `$alias` to project/rename fields
- Detects circular references and missing IDs
- Validates aliases, IDs, and prevents duplicates
- Works with arrays (`[{...}]`) or object-maps (`{ "id": {...} }`)
- Optional `--strict-projection` for safe `$alias`
- Compile output to either `.json` or `.bson`

---

## 📦 Example

**data/products.json**
```json
[
  { "product_id": 1, "name": "t-shirt" },
  { "product_id": 2, "name": "pants" }
]
```

**data/categories.json**

```json
[
  { "category_id": 10, "category_name": "apparel" }
]
```
**data/logos.json**

```json
[
  {
    "logo_id": 1,
    "brand": "Acorn Systems",
    "mime_type": "image/png",
    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottQAAAABJRU5ErkJggg=="
  },
  {
    "logo_id": 2,
    "brand": "Blue Meadow",
    "mime_type": "image/png",
    "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8AARAwMDIxBAAAgPgD13e9QYQAAAABJRU5ErkJggg=="
  }
]
```

**data/suppliers.json**

```json
[
  { "supplier_id": 100, "supplier_name": "Acme Corp", "contact_email": "info@acme.com" }
]
```

**preprocessor.json**

```json
{
  "$imports": {
    "product": "data/products.json",
    "category": "data/categories.json",
    "supplier": "data/suppliers.json",
    "logo": "data/logos.json"
  },
  "product": { "$ref": "product:1" },
  "category": { "$ref": "category: 10" },
  "supplier": {
    "$ref": "supplier : 100",
    "$alias": { "supplier_name": "name", "contact_email": "email" }
  },
  "app_branding": {
    "primary_logo": { 
      "$ref": "logo :    1", 
      "$alias": { "brand": "brand", "data_base64": "image" }
    }
  }  
}
```

(Note: whitespace around the alias or id is ignored)

Run:

```bash
python jsonloom.py preprocessor.json
```

Output (`preprocessor.compiled.json`):

```json
{
  "product": {
    "product_id": 1,
    "name": "t-shirt"
  },
  "category": {
    "category_id": 10,
    "category_name": "apparel"
  },
  "supplier": {
    "name": "Acme Corp",
    "email": "info@acme.com"
  },
  "app_branding": {
    "primary_logo": {
      "brand": "Acorn Systems",
      "image": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottQAAAABJRU5ErkJggg=="
    }
  }
}
```

---

## ⚙️ Usage

```bash
python jsonloom.py <input.json|.bson> [output.json|.bson] [options]

# If output is omitted, writes <input>.compiled.json (or .bson if input was .bson)
```

Options (can be combined in any order):

* `--strict-projection` → error if `$alias` references fields that don’t exist (default: warn only)
* `--indent N` → set JSON output indentation (default: 2; use 0 for minified output; ignored for BSON)
* `--base64-binary` → when writing JSON, BSON Binary values are automatically converted to base64 strings

---

## ▶ Next Steps: Using Compiled Documents

JSON-LOOM produces **fully denormalized JSON/BSON documents**.  

You can:

- Use them directly in your app (as static data or configs), or  
- Submit them to a document database (e.g., MongoDB).

Example (MongoDB, Python):

```python
collection.replace_one({ "_id": doc["_id"] }, doc, upsert=True)
```

This pattern lets you re-compile normalized data and update the document store in one step.

---

## 💾 Working with BSON and Binary Data

JSON-LOOM supports both **JSON** and **BSON** as input and output formats:

- `.json` → standard JSON, portable and human-readable
- `.bson` → MongoDB’s binary JSON, efficient and compact

### 🖼️ Binary data

Because JSON does not support raw binary, binary fields must be stored as **base64 strings** when working with `.json` files:

```json
{
  "logo_id": 1,
  "brand": "Acorn Systems",
  "mime_type": "image/png",
  "data_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQ..."
}
```

If you import from `.bson` files that contain true `Binary` values:

* Compiling to `.bson` preserves the raw binary.
* Compiling to `.json` will, by default, raise an error unless you enable `--base64-binary`, which converts raw binary to base64 strings.

---

### 🧭 Design Decision

JSON-LOOM defaults to **base64-in-JSON** for binary data in examples.
Why?

* Base64 is valid JSON and works everywhere (APIs, configs, GitHub).
* Easier for newcomers to understand and copy-paste.
* Keeps JSON-LOOM’s examples portable outside MongoDB.

Native BSON binary is still supported for advanced users who need efficiency in MongoDB-heavy environments.

---

## 📜 Syntax

Preprocessor files are strict JSON documents with a few special keywords.  

### 🔗 `$imports`
Defines which relational JSON sources to load. Keys are **aliases** (used in `$ref`), and 
values are file paths relative to the preprocessor file.

```json
"$imports": {
  "product": "data/products.json",
  "logo": "data/logos.json",
  "category": "data/categories.json",
  "supplier": "data/suppliers.json"
}
```

**Is like (SQL table aliases):**

```sql
FROM products   AS product,
     logos      AS logo,
     categories AS category,
     suppliers  AS supplier
```

**Is like (JavaScript / ES Modules):**

```js
import { product } from "data/products.json";
import { logo } from "data/suppliers.json";
import { category } from "data/categories.json";
import { supplier } from "data/suppliers.json";
```

🗝️ **Note on IDs**  

Each imported JSON/BSON source must have a clear identifier field so `$ref` can work.  

- If the file is an **array of objects**, JSON-LOOM looks for `id` first, then falls back to the first field ending in `_id` (e.g., `product_id`, `category_id`, `supplier_id`).  
- If the file is an **object keyed by IDs**, those keys are used directly as IDs.  

The import alias name (`"product"`, `"category"`, etc.) does **not** have to match the ID field name. For example:

```json
"$imports": {
  "lighting_product": "data/products.json"
}

"product": { "$ref": "lighting_product:1" }
```
 
This approach works fine, even if the records inside `products.json` use `product_id` as the identifier. The important part is that each record has an ID field and `$ref` uses the right alias.

---

### 🧩 `$ref`

References a record from an imported file.
Format: `"alias:id"` — whitespace around the alias or id is ignored.

```json
"product": { "$ref": "product:1" },
"category": { "$ref": "category: 10" },
"supplier": { "$ref": "supplier  :   100" }
```

**Is like (SQL primary key lookup / foreign key dereference):**

```sql
SELECT * FROM products WHERE product_id = 1;
SELECT * FROM suppliers WHERE supplier_id = 100;
```

---

### ✂️ `$alias`

Optional projection/renaming. Maps fields in the source record to new keys in the compiled output.

```json
"supplier": {
  "$ref": "supplier:100",
  "$alias": { "supplier_name": "name", "contact_email": "email" }
}
```

Output:

```json
"supplier": {
  "name": "Acme Corp",
  "email": "info@acme.com"
}
```

**Is like (SQL SELECT aliasing):**

```sql
SELECT supplier_name AS name, contact_email AS email
FROM suppliers WHERE supplier_id = 100;
```

---

## 📥 Installation

### Non-binary usage
No dependencies required — just Python **3.9+**.  
If you only plan to work with `.json` files, you’re ready to go.

```bash
git clone https://github.com/Hydra9268/json-loom.git
cd json-loom
````

### BSON usage

If you want to import/export `.bson` files or handle binary data, you need an extra package:

```bash
# Recommended
pip install pymongo

# Alternative (not recommended, may conflict with pymongo)
pip install bson
```

> ⚠️ BSON support comes from the `pymongo` package.
> A standalone `bson` package also exists, but it’s not official and may conflict —
> prefer installing `pymongo`.

---

### 📂 Recommended File Structure

To keep projects organized, we suggest separating your **relational JSON sources** 
(products, categories, suppliers, etc.) from your **preprocessor JSON files** 
(the documents that reference them).

Example layout:

```
json-loom/
├── jsonloom.py
├── preprocessor.json
└── data/
    ├── products.json
    ├── logos.json
    ├── categories.json    
    └── suppliers.json
```

- Place normalized/relational JSON files inside a `data/` folder (or any folder you prefer).
- Keep your preprocessor files (like `preprocessor.json`) at the project root for clarity.
- References in `$imports` are always relative to the preprocessor file’s location.
