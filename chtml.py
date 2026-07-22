#!/usr/bin/env python3
import sys
import re
import os
import tempfile
import argparse
import subprocess
import platform
from html.parser import HTMLParser

# Attributes kept when --strip-attrs is used
SAFE_ATTRS = {
    'href', 'src', 'alt', 'title', 'colspan', 'rowspan',
    'type', 'name', 'value', 'placeholder'
}


class HTMLSanitizer(HTMLParser):
    def __init__(self, strip_attrs=False, strip_svg=False, keep_comments=False, keep_scripts=False):
        super().__init__(convert_charrefs=False)
        self.out = []
        self.strip_attrs = strip_attrs
        self.strip_svg = strip_svg
        self.keep_comments = keep_comments
        self.keep_scripts = keep_scripts
        self._skip_stack = []  # tags whose entire content is being dropped (style/script)
        self._svg_depth = 0

    def _in_skip(self):
        return bool(self._skip_stack) or self._svg_depth > 0

    def handle_starttag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=False)

    def handle_startendtag(self, tag, attrs):
        self._emit_start(tag, attrs, self_closing=True)

    def _emit_start(self, tag, attrs, self_closing):
        lower = tag.lower()

        if lower == 'style' or (lower == 'script' and not self.keep_scripts):
            if not self_closing:
                self._skip_stack.append(lower)
            return

        if lower == 'svg' and self.strip_svg:
            if self._svg_depth == 0:
                self.out.append('<svg/>')
            if not self_closing:
                self._svg_depth += 1
            return

        if self._in_skip():
            return

        filtered = []
        for name, value in attrs:
            name_lower = name.lower()
            if name_lower == 'style' or name_lower.startswith('on'):
                continue
            if self.strip_attrs and name_lower not in SAFE_ATTRS:
                continue
            filtered.append((name, value))

        attr_str = ''.join(_render_attr(n, v) for n, v in filtered)
        self.out.append(f'<{tag}{attr_str}{"/" if self_closing else ""}>')

    def handle_endtag(self, tag):
        lower = tag.lower()

        if lower == 'svg' and self.strip_svg:
            if self._svg_depth > 0:
                self._svg_depth -= 1
            return

        if self._svg_depth > 0:
            return

        if self._skip_stack and self._skip_stack[-1] == lower:
            self._skip_stack.pop()
            return

        if self._in_skip():
            return

        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._in_skip():
            return
        self.out.append(data)

    def handle_comment(self, data):
        if self._svg_depth > 0:
            return
        if self.keep_comments:
            self.out.append(f'<!--{data}-->')

    def handle_entityref(self, name):
        if self._in_skip():
            return
        self.out.append(f'&{name};')

    def handle_charref(self, name):
        if self._in_skip():
            return
        self.out.append(f'&#{name};')

    def handle_decl(self, decl):
        self.out.append(f'<!{decl}>')

    def get_output(self):
        return ''.join(self.out)


def _render_attr(name, value):
    if value is None:
        return f' {name}'
    escaped = value.replace('&', '&amp;').replace('"', '&quot;')
    return f' {name}="{escaped}"'


def squeeze_whitespace(html):
    # Collapse pretty-print indentation (whitespace between tags that spans a
    # newline) but leave single spaces between inline elements alone.
    html = re.sub(r'>[ \t\r\n]*\n[ \t\r\n]*<', '><', html)
    html = re.sub(r'\n[ \t]*\n+', '\n', html)
    return html.strip()


def sanitize(html, strip_attrs=False, strip_svg=False, keep_comments=False,
             keep_scripts=False, no_squeeze=False):
    parser = HTMLSanitizer(
        strip_attrs=strip_attrs,
        strip_svg=strip_svg,
        keep_comments=keep_comments,
        keep_scripts=keep_scripts,
    )
    parser.feed(html)
    parser.close()
    result = parser.get_output()
    if not no_squeeze:
        result = squeeze_whitespace(result)
    return result


def write_temp_file(content):
    fd, path = tempfile.mkstemp(prefix='chtml-', suffix='.html', dir=tempfile.gettempdir())
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(content)
    return path


def copy_to_clipboard(text):
    system = platform.system()
    try:
        if system == 'Darwin':
            cmd = ['pbcopy']
        elif system == 'Windows':
            cmd = ['clip']
        else:
            cmd = ['xclip', '-selection', 'clipboard']

        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode('utf-8'))
        return True
    except FileNotFoundError:
        return False


def main():
    parser = argparse.ArgumentParser(
        prog='chtml',
        description=(
            'Sanitize copied HTML for pasting into an LLM: strips <style>/<script> '
            'blocks, style= and on*= attributes, comments, and pretty-print whitespace.'
        ),
    )
    parser.add_argument(
        '-a', '--strip-attrs', action='store_true',
        help='strip all attributes except a safe allowlist (href, src, alt, title, ...) '
             '- cuts class/id/data-*/aria-* soup'
    )
    parser.add_argument(
        '--strip-svg', action='store_true',
        help='collapse inline <svg>...</svg> content down to <svg/> (icon path data is pure token waste)'
    )
    parser.add_argument('--keep-comments', action='store_true', help='keep HTML comments (stripped by default)')
    parser.add_argument('--keep-scripts', action='store_true', help='keep <script> blocks (stripped by default)')
    parser.add_argument('--no-squeeze', action='store_true', help="don't collapse pretty-print indentation whitespace")
    parser.add_argument('--no-clipboard', action='store_true', help="don't copy the result to the clipboard")
    parser.add_argument(
        '-t', '--tmpfile', action='store_true',
        help="write the result to a file in the OS temp dir and copy that file's path instead of "
             "the content - hand the LLM a path instead of pasting a huge blob"
    )
    parser.add_argument('file', nargs='?', help='read HTML from a file instead of stdin/clipboard')
    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            input_data = f.read()
    elif not sys.stdin.isatty():
        input_data = sys.stdin.read()
    else:
        print("Usage: pbpaste | chtml   (or) chtml file.html", file=sys.stderr)
        sys.exit(1)

    result = sanitize(
        input_data,
        strip_attrs=args.strip_attrs,
        strip_svg=args.strip_svg,
        keep_comments=args.keep_comments,
        keep_scripts=args.keep_scripts,
        no_squeeze=args.no_squeeze,
    )

    before, after = len(input_data), len(result)
    saved_pct = 100 * (1 - after / before) if before else 0

    if args.tmpfile:
        path = write_temp_file(result)
        print(path)
        clip_text, clip_label = path, 'file path'
    else:
        print(result)
        clip_text, clip_label = result, 'result'

    print(f"\n\033[92m{before:,} -> {after:,} chars ({saved_pct:.0f}% smaller)\033[0m", file=sys.stderr)

    if not args.no_clipboard:
        if copy_to_clipboard(clip_text):
            print(f"\033[92m✔ Copied {clip_label} to clipboard\033[0m", file=sys.stderr)
        else:
            print("\033[93m⚠ Could not find clipboard tool (install xclip on Linux)\033[0m", file=sys.stderr)


if __name__ == '__main__':
    main()
