# JSON-LOOM

*Weave relational JSON into denormalized documents.*

JSON-LOOM is a lightweight preprocessor that lets you author **normalized JSON** 
(similar to relational tables) and compile it into **flat, document-friendly JSON** 
optimized for document databases like MongoDB. Think of it as **Sass for JSON**: 
write once, keep it DRY, and compile to ready-to-use output.

---

## Features
- `$imports` for relational JSON sources
- `$ref` syntax with flexible spacing (`product:1`, `product : 1`)
- `$pick` to project/rename fields
- `$mode: "link"` to inline just the ID
- Detects circular refs and missing IDs
- Works with arrays (`[{...}]`) or object-maps (`{ "id": {...} }`)

---

## Example

**products.json**
```json
[
  { "product_id": 1, "name": "t-shirt" },
  { "product_id": 2, "name": "pants" }
]
````

**categories.json**

```json
[
  { "category_id": 10, "category_name": "apparel" }
]
```

**suppliers.json**

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
    "supplier": "data/suppliers.json"
  },
  "product": { "$ref": "product:1" },
  "category": { "$ref": "category: 10" },
  "supplier": {
    "$ref": "supplier  :   100",
    "$pick": { "supplier_name": "name", "contact_email": "email" }
  }
}
```

Run:

```bash
python script.py examples/preprocessor.json
```

Output (`preprocessor.compiled.json`):

```json
{
  "product": { "product_id": 1, "name": "t-shirt" },
  "category": { "category_id": 10, "category_name": "apparel" },
  "supplier": { "name": "Acme Corp", "email": "info@acme.com" }
}
```

---

## Usage

```bash
python script.py <input.json> [output.json]

# If output is omitted, writes <input>.compiled.json
```

Options:

* `--strict-projection` → error if `$pick` references fields that don’t exist (default: warn only)
* `--indent N` → set output indentation (default: 2; use 0 for minified output)

---

## Installation

No dependencies, just Python 3.9+:

```bash
git clone https://github.com/Hydra9268/json-loom.git
cd json-loom
python script.py examples/preprocessor.json
```

---

### ✅ Recommended File Structure

To keep projects organized, we suggest separating your **relational JSON sources** 
(products, categories, suppliers, etc.) from your **preprocessor JSON files** 
(the documents that reference them).

Example layout:

```
json-loom/
├── script.py
├── examples/
│   ├── preprocessor.json
│   └── data/
│       ├── products.json
│       ├── categories.json
│       └── suppliers.json
```

- Place normalized/relational JSON files inside a `data/` folder (or any folder you prefer).
- Keep your preprocessor files (like `preprocessor.json`) at the project root for clarity.
- References in `$imports` are always relative to the preprocessor file’s location.

---

## License

MIT License

Copyright (c) 2025 Ryan Allen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
