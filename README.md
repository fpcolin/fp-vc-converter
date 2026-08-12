# VendorCafe CSV Converter

A small Windows desktop app for Flooring Partners that consolidates a Rollmaster
invoice export into the one-line-per-invoice format VendorCafe expects for
upload.

Built with Python and Tkinter, packaged as a standard Windows program with an
installer and built-in updates. No third-party libraries.

## What it does

A Rollmaster export lists every line item of every invoice as its own row.
VendorCafe wants one row per invoice. For each invoice the converter keeps the
first row, sets the line-item fields to represent the invoice as a whole, and
tidies the identifiers:

- Duplicate rows for the same **Invoice No** are dropped, keeping the first
- **Item Amount** and **Unit Price** are set to the **Invoice Total**
- **Item Sequence** and **Quantity** are set to `1`
- The `1-` prefix is stripped from **Invoice No**
- Apostrophes are stripped from **Invoice Desc** and **Property Code**
- **Item Desc** is set to the cleaned **Invoice No**
- For work-order customers, **Job No** is dropped and **PO No** becomes **WO No**

Everything is handled as text, so amounts, leading zeros, and dates are written
back exactly as exported.

## Installing

Download `FPVendorCafeConverter-<version>-setup.exe` from the
[latest release](https://github.com/fpcolin/fp-vendorcafe-converter/releases/latest)
and run it.

It installs per-user under `%LOCALAPPDATA%\Programs`, so no administrator rights
are needed. Settings are stored in:

```
%LOCALAPPDATA%\Flooring Partners\VendorCafe CSV Converter\config.json
```

Uninstall from Settings → Apps like any other program.

## Using it

1. Export the VendorCafe invoices to a CSV file in Rollmaster. **Do not edit the
   file** — editing it may stop the converter recognising the columns.
2. Click **Change file** and select the file you just exported.
3. Click **Convert CSV (PO)** if the customer uses a PO number, or
   **Convert CSV (WO)** if they use a work order number.
4. Upload the converted file to VendorCafe.

A summary appears when it finishes, showing how many rows were consolidated into
how many invoices. If anything goes wrong — wrong file, missing columns, file
open in Excel — it says so rather than failing quietly.

By default the export is overwritten in place. Untick **Overwrite CSV file**
under the File menu to write a separate ` converted.csv` copy instead.

### Menus

| Menu | Item | What it does |
|---|---|---|
| File | Change file… | Pick the exported CSV to convert |
| File | Check for updates… | Look for a newer version now |
| File | Overwrite CSV file | Replace the export, or write a separate copy |
| File | Open folder after converting | Open the containing folder when done |
| File | Exit | Close the program |
| Help | — | Usage instructions inside the app |

## Updates

On launch the app quietly checks the latest release for a newer version and
offers to install it. The download is verified against a SHA-256 checksum before
anything is run, and the app relaunches once the update finishes.

If the check fails — no network, VPN down, GitHub unreachable — it is ignored
silently and the app carries on.

## Building from source

Requires Python 3.12+, [Inno Setup](https://jrsoftware.org/isdl.php), and:

```
pip install pyinstaller
```

Then:

```
pyinstaller build\vc_converter.spec --noconfirm --clean --workpath dist\work
iscc build\installer.iss
```

Releases are built automatically by GitHub Actions when a version tag is pushed.
See [BUILD.md](BUILD.md) for the full process, including versioning, code
signing, and troubleshooting.

## Licence

Source code and documentation are released under the MIT Licence.

The Flooring Partners name and icon (`src/fp.ico`) are excluded and remain
company property — no trademark rights are granted. If you fork this project,
replace that file with your own and change the `VENDOR` and `APP_NAME` constants
in `src/vc_converter.pyw`.

See [LICENSE.txt](LICENSE.txt) for both.

## AI disclosure

Portions of this project were developed with the help of an AI assistant
(Anthropic's Claude).

The original working version of the program was written by hand. AI assistance
was then used to refactor that code, remove its third-party dependencies, and
build out the packaging and release tooling — the PyInstaller spec, the Inno
Setup installer, the update mechanism, the GitHub Actions workflow, and the
documentation.

All AI-generated code was reviewed and tested before being committed, and the
maintainer is responsible for everything in this repository regardless of how it
was produced. It is noted here for transparency, not as a disclaimer of
ownership or accountability.
