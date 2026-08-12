"""Flooring Partners VendorCafe CSV Converter.

Consolidates the many line items of each exported invoice down to a single row
for upload into VendorCafe.

No third-party requirements - the standard library covers all of it.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import updater

VENDOR = 'Flooring Partners'
APP_NAME = 'VendorCafe CSV Converter'
VERSION = '2.0.1'

# Bumped only when the shape of the config file changes, never for an ordinary
# release. Keying the reset on VERSION would wipe everyone's settings on every
# patch, which is not what they would expect.
CONFIG_SCHEMA = 1

CSV_TYPES = [('CSV files', '.csv')]

DEFAULTS = {
    'schema': CONFIG_SCHEMA,
    'version': VERSION,
    'filepath': '',
    'option_overwrite': True,
    'option_open_folder': False,
}

# Every column the exported file must contain. Order here is only used for
# reporting; the output keeps whatever order the source file had.
REQUIRED_COLUMNS = (
    'PO No', 'Job No', 'Type', 'Invoice No', 'Invoice Desc', 'Invoice Date',
    'Due Date', 'Invoice Total', 'Tax Total', 'Shipping Total', 'Property Name',
    'Property Code', 'Unit', 'Item Sequence', 'Item Desc', 'Quantity',
    'Unit Price', 'Item Amount',
)


def resource_path(name: str) -> Path:
    """Locate a bundled data file, whether frozen by PyInstaller or run from source."""
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
    return Path(base) / name


def open_in_shell(target: Path) -> None:
    """Hand a file or folder to the OS default handler.

    os.startfile avoids shelling out through cmd, so a windowed .exe never
    flashes a console. AttributeError covers non-Windows.
    """
    try:
        os.startfile(str(target))
    except (AttributeError, OSError):
        pass


class ConversionError(Exception):
    """Raised with a message suitable for showing directly to the user."""


class Config:
    """Settings kept in memory, written to disk only when a value changes."""

    def __init__(self) -> None:
        local_appdata = os.getenv('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local'
        self.path = Path(local_appdata) / VENDOR / APP_NAME / 'config.json'
        self._data = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            stored = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            stored = None

        # Reset only when the file's structure is unrecognisable, not when the
        # app version moves. Settings survive upgrades.
        if isinstance(stored, dict) and stored.get('schema') == CONFIG_SCHEMA:
            self._data.update({k: v for k, v in stored.items() if k in DEFAULTS})
            if self._data.get('version') != VERSION:
                self._data['version'] = VERSION
                self.save()
        else:
            self.save()

        # Clean up config files from versions that used YAML.
        try:
            self.path.with_name('config.yml').unlink(missing_ok=True)
        except OSError:
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2), encoding='utf-8')
        except OSError:
            pass  # Locked-down profile: carry on with in-memory settings.

    def __getitem__(self, key: str):
        return self._data[key]

    def set(self, key: str, value) -> None:
        if self._data.get(key) != value:
            self._data[key] = value
            self.save()


class Converter:
    """The CSV transformation, with no user interface attached.

    Everything is handled as text. The previous version used pandas, which
    parsed the money columns as floats and wrote them back as float repr - so
    1234.50 became 1234.5 and 0.00 became 0.0 on every conversion. It also
    failed outright on a purely numeric Invoice No, because .replace() does not
    exist on an int. Reading with the csv module keeps every field exactly as
    exported.
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    @staticmethod
    def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
        # Rollmaster exports often carry a UTF-8 BOM; utf-8-sig strips it so the
        # first column name does not arrive as '\ufeffPO No' and fail the check.
        for encoding in ('utf-8-sig', 'cp1252'):
            try:
                with open(path, newline='', encoding=encoding) as handle:
                    reader = csv.DictReader(handle)
                    fieldnames = list(reader.fieldnames or [])
                    return fieldnames, list(reader)
            except UnicodeDecodeError:
                continue
        raise ConversionError('Could not read the file - unexpected text encoding.')

    def convert(self, work_order: bool) -> tuple[Path, int, int]:
        """Consolidate the selected file. Returns (output path, rows in, rows out)."""
        raw = self.config['filepath']
        if not raw:
            raise ConversionError('No file selected. Click "Change file" first.')

        source = Path(raw)
        if not source.is_file():
            raise ConversionError(f'The selected file no longer exists:\n{source}')

        fieldnames, rows = self._read(source)
        if not fieldnames:
            raise ConversionError('That file appears to be empty.')

        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise ConversionError(
                'This does not look like a VendorCafe export.\n\n'
                'Missing columns:\n  ' + '\n  '.join(missing) +
                '\n\nExport the invoices again from Rollmaster without editing the file.'
            )
        if not rows:
            raise ConversionError('That file has column headings but no invoice rows.')

        # Keep the first row of each invoice, preserving the original order.
        seen: set[str] = set()
        kept: list[dict[str, str]] = []
        for row in rows:
            number = (row.get('Invoice No') or '').strip()
            if number in seen:
                continue
            seen.add(number)
            kept.append(row)

        for row in kept:
            total = row.get('Invoice Total') or ''
            row['Item Amount'] = total
            row['Unit Price'] = total
            row['Item Sequence'] = '1'
            row['Quantity'] = '1'
            row['Invoice No'] = (row.get('Invoice No') or '').replace('1-', '')
            row['Invoice Desc'] = (row.get('Invoice Desc') or '').replace("'", '')
            row['Property Code'] = (row.get('Property Code') or '').replace("'", '')
            row['Item Desc'] = row['Invoice No']

        out_fields = list(fieldnames)
        if work_order:
            # Drop the job number and relabel the PO column in place, so the
            # column order the upload expects is unchanged.
            if 'Job No' in out_fields:
                out_fields.remove('Job No')
            if 'PO No' in out_fields:
                out_fields[out_fields.index('PO No')] = 'WO No'
                for row in kept:
                    row['WO No'] = row.pop('PO No', '')

        target = source if self.config['option_overwrite'] else \
            source.with_name(f'{source.stem} converted{source.suffix}')

        # Write to a temporary file and swap it in, so a failure part way
        # through cannot leave the user with a truncated export.
        temp = target.with_name(target.name + '.tmp')
        try:
            with open(temp, 'w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=out_fields,
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(kept)
            os.replace(temp, target)
        except OSError as exc:
            Path(temp).unlink(missing_ok=True)
            raise ConversionError(
                f'Could not write the converted file:\n{exc}\n\n'
                'If the file is open in Excel, close it and try again.'
            ) from exc

        return target, len(rows), len(kept)


class Gui:
    def __init__(self, config: Config, converter: Converter) -> None:
        self.config = config
        self.converter = converter
        self.icon_path = resource_path('fp.ico')

        self.root = tk.Tk()
        # Hide before anything can map it. iconbitmap() and other wm calls force
        # Tk to realise the window, so withdrawing later means it appears,
        # vanishes, then reappears centred - a visible flash.
        self.root.withdraw()
        self.root.title(f'{VENDOR} {APP_NAME} v{VERSION}')
        self.root.resizable(False, False)
        self._set_icon(self.root)

        self.body = ttk.Frame(self.root)
        self.filepath_var = tk.StringVar(self.root)
        self.option_vars: dict[str, tk.BooleanVar] = {}  # Held so Tk cannot GC them.
        self._refresh_filepath()

    # ------------------------------------------------------------------ helpers

    def _set_icon(self, window: tk.Misc) -> None:
        try:
            window.iconbitmap(str(self.icon_path))
        except tk.TclError:
            pass  # Icon absent when running from source.

    def _refresh_filepath(self) -> None:
        path = self.config['filepath']
        self.filepath_var.set(f'Selected file: {path}' if path
                              else 'Selected file: none selected')

    def _dialog(self, title: str) -> tuple[tk.Toplevel, ttk.Frame]:
        """Create a modal child window offset from the main one, plus its body."""
        window = tk.Toplevel(self.root)

        # A Toplevel is mapped as soon as it is created, before geometry() moves
        # it and before any widgets exist, so it paints an empty frame in the
        # wrong place and then jumps. Stay hidden until fully built.
        window.withdraw()
        window.title(title)
        window.resizable(False, False)
        self._set_icon(window)
        window.transient(self.root)

        x, y = (int(part) for part in self.root.geometry().split('+')[1:])
        window.geometry('+%d+%d' % (x + self.root.winfo_width() // 4,
                                    y + self.root.winfo_height() // 4))

        body = ttk.Frame(window)
        body.grid(column=0, row=0, sticky=tk.NW, padx=20, pady=20)
        window.bind('<Escape>', lambda _event: window.destroy())

        # Callers add widgets after this returns, so reveal on the next idle
        # cycle once the layout is final. grab_set waits too, or the modal grab
        # applies to a window the user cannot see.
        def reveal() -> None:
            window.deiconify()
            window.grab_set()
            window.focus_force()
            target = getattr(window, '_initial_focus', None)
            if target is not None:
                target.focus_set()

        window.after_idle(reveal)
        return window, body

    def _option_checkbutton(self, menu: tk.Menu, label: str, key: str) -> None:
        var = tk.BooleanVar(value=self.config[key])
        self.option_vars[key] = var
        menu.add_checkbutton(
            label=label, onvalue=True, offvalue=False, variable=var,
            command=lambda: self.config.set(key, var.get()),
        )

    # --------------------------------------------------------------------- menu

    def create_menubar(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label='Change file\u2026', command=self.change_file)
        file_menu.add_command(label='Check for updates\u2026',
                              command=lambda: self.check_for_updates(manual=True))
        file_menu.add_separator()
        self._option_checkbutton(file_menu, 'Overwrite CSV file', 'option_overwrite')
        self._option_checkbutton(file_menu, 'Open folder after converting',
                                 'option_open_folder')
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.destroy)
        menubar.add_cascade(label='File', menu=file_menu)

        menubar.add_command(label='Help', command=self.draw_help_window)
        self.root.config(menu=menubar)

    # --------------------------------------------------------------------- body

    def create_body(self) -> None:
        self.body.grid(column=0, row=0, sticky=tk.NW, padx=20, pady=10)

        ttk.Label(self.body, textvariable=self.filepath_var).grid(
            column=0, row=0, sticky=tk.NW, padx=(0, 10), columnspan=2)
        ttk.Button(self.body, text='Change file', command=self.change_file).grid(
            column=2, row=0, sticky=tk.NW)

        ttk.Button(self.body, text='Convert CSV (PO)',
                   command=lambda: self.run_conversion(False)).grid(
            column=0, row=1, sticky=tk.NW, pady=(10, 10))
        ttk.Button(self.body, text='Convert CSV (WO)',
                   command=lambda: self.run_conversion(True)).grid(
            column=1, row=1, sticky=tk.NW, pady=(10, 10), padx=(10, 0))

        self.root.bind('<Escape>', lambda _event: self.root.destroy())

    # --------------------------------------------------------------- converting

    def change_file(self) -> None:
        current = Path(self.config['filepath'] or Path.home())
        folder = current.parent if current.is_file() else current
        while not folder.is_dir() and folder != folder.parent:
            folder = folder.parent

        path = filedialog.askopenfilename(
            parent=self.root,
            title='Select the exported VendorCafe CSV',
            initialdir=str(folder),
            filetypes=CSV_TYPES,
        )
        if path:
            self.config.set('filepath', os.path.normpath(path))
            self._refresh_filepath()

    def run_conversion(self, work_order: bool) -> None:
        try:
            target, rows_in, rows_out = self.converter.convert(work_order)
        except ConversionError as exc:
            # The previous version returned silently here, so a failed run looked
            # exactly like a successful one.
            messagebox.showerror('Could not convert', str(exc), parent=self.root)
            return
        except Exception as exc:                      # noqa: BLE001 - last resort
            messagebox.showerror('Unexpected error',
                                 f'{type(exc).__name__}: {exc}', parent=self.root)
            return

        kind = 'WO' if work_order else 'PO'
        messagebox.showinfo(
            'Conversion complete',
            f'{rows_in} rows consolidated into {rows_out} invoices ({kind}).\n\n'
            f'Saved to:\n{target}',
            parent=self.root,
        )
        if self.config['option_open_folder']:
            open_in_shell(target.parent)

    # ------------------------------------------------------------------ updates

    def check_for_updates(self, manual: bool = False) -> None:
        """Look for a newer release. Silent on failure unless the user asked.

        Always off the UI thread: a synchronous call blocks the event loop for
        up to NETWORK_TIMEOUT seconds, which freezes and greys the window.
        """
        def done(manifest: dict | None) -> None:
            if manifest:
                self.offer_update(manifest)
            elif manual:
                messagebox.showinfo('No updates',
                                    f'You are running the latest version ({VERSION}).',
                                    parent=self.root)

        def worker() -> None:
            self.root.after(0, done, updater.check(VERSION))

        threading.Thread(target=worker, daemon=True).start()

    def offer_update(self, manifest: dict) -> None:
        notes = manifest.get('notes', '').strip()
        prompt = f'Version {manifest["version"]} is available.\nYou have {VERSION}.'
        if notes:
            prompt += f'\n\n{notes}'
        prompt += '\n\nInstall it now? The program will close briefly.'

        if not messagebox.askyesno('Update available', prompt, parent=self.root):
            return

        self.root.config(cursor='watch')
        self.root.update_idletasks()
        try:
            installer = updater.download(manifest)
            updater.apply(installer)
        except updater.UpdateError as exc:
            self.root.config(cursor='')
            messagebox.showerror('Update failed', str(exc), parent=self.root)
            return
        self.root.destroy()

    # ------------------------------------------------------------------ dialogs

    def draw_help_window(self) -> None:
        window, body = self._dialog('Help')
        message = (
            'This program consolidates all the lines of each invoice into one line\n'
            'for uploading into VendorCafe.\n\n'
            'Steps to use this program are below.\n\n'
            '1. Export the VendorCafe invoices to a CSV file in Rollmaster. Do NOT\n'
            '   edit this file at all. Editing the exported CSV file may cause this\n'
            '   program to not function properly.\n'
            '2. Click "Change file" and select the file you just exported.\n'
            '3. Depending on how you are uploading it to VendorCafe, select:\n\n'
            '\t"Convert CSV (PO)" if the customer uses a PO number.\n'
            '\t"Convert CSV (WO)" if the customer uses a work order number.\n\n'
            '4. Once you click convert, the file is overwritten with the\n'
            '   consolidated version, ready to upload into VendorCafe.\n\n'
            'File:\n'
            'Change file - choose the exported CSV to convert\n'
            'Check for updates - look for a newer version now\n'
            'Overwrite CSV file - untick to write a separate " converted" copy\n'
            '   instead of replacing the export\n'
            'Open folder after converting - open the containing folder when done\n'
            'Exit - close the program'
        )
        tk.Label(body, text=message, anchor='w', justify='left').grid(
            column=0, row=0, sticky=tk.NW, columnspan=2)
        ttk.Button(body, text='Close', command=window.destroy).grid(
            column=1, row=1, sticky=tk.NE, pady=10)
        window.bind('<Return>', lambda _event: window.destroy())

    # ---------------------------------------------------------------------- run

    def start(self) -> None:
        self.create_menubar()
        self.create_body()

        # Centre using the real requested size rather than hard-coded numbers.
        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        self.root.geometry('+%d+%d' % (
            (self.root.winfo_screenwidth() - width) // 2,
            (self.root.winfo_screenheight() - height) // 2,
        ))
        self.root.deiconify()

        # Fire after the window is drawn so a slow network never delays startup.
        self.root.after(1200, self.check_for_updates)
        self.root.mainloop()


if __name__ == '__main__':
    config = Config()
    Gui(config, Converter(config)).start()
