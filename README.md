# chtml (Clean HTML)

A simple Python utility to sanitize copied HTML before pasting it into an LLM
(ChatGPT, Claude, Gemini, etc). Strips the stuff that bloats your token count
without adding meaning.

## What it does
- 🧹 **Strips `<style>` blocks and `style="..."` attributes** — the main offender.
- 🚫 **Removes `<script>` blocks and `on*="..."` event handlers.**
- 💬 **Strips HTML comments.**
- 📏 **Collapses pretty-print indentation** between tags (keeps meaningful inline spacing).
- 🔒 **Optional `-a` attribute stripping** — drops `class`/`id`/`data-*`/`aria-*` soup, keeps `href`, `src`, `alt`, `title`, etc.
- 🖼️ **Optional `--strip-svg`** — collapses inline `<svg>...</svg>` icon path data down to `<svg/>`.
- 📋 **Auto copy** — copies the cleaned result to your clipboard and prints the char-count savings to stderr.

## Installation

1. Download `chtml.py` and make it executable:
```sh
chmod +x chtml.py
```

2. Copy it to your bin folder (if it isn't there already) and drop the extension.
   Use `cp`, not `mv` — keep `chtml.py` in this repo as the source of truth:
```sh
sudo cp chtml.py /usr/local/bin/chtml
```

## Usage

Copy some HTML to your clipboard (e.g. "Copy outerHTML" from DevTools), then run:
```sh
# MacOS
pbpaste | chtml

# Linux
xclip -o | chtml
```

Or point it at a file:
```sh
chtml page.html
```

### Flags

| Flag | Effect |
|---|---|
| `-a`, `--strip-attrs` | Strip all attributes except a safe allowlist (`href`, `src`, `alt`, `title`, `type`, `name`, `value`, `placeholder`, `colspan`, `rowspan`) |
| `--strip-svg` | Collapse inline `<svg>` content to `<svg/>` |
| `--keep-comments` | Keep HTML comments (stripped by default) |
| `--keep-scripts` | Keep `<script>` blocks (stripped by default) |
| `--no-squeeze` | Don't collapse pretty-print whitespace |
| `--no-clipboard` | Don't copy the result to the clipboard |

For the most aggressive cut (structure and text only):
```sh
pbpaste | chtml -a --strip-svg
```

## Notes
- Uses Python's stdlib `html.parser`, so there are no dependencies to install.
- HTML attribute names are lowercased on output (a quirk of `html.parser`) — fine for an
  LLM to read, but don't feed the output back into a browser expecting `viewBox` casing etc.
