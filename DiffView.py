import sublime
import sublime_plugin
import subprocess
import re

class DiffView(sublime_plugin.WindowCommand):
    last_diff = ''

    def run(self):
        # Use this as show_quick_panel doesn't allow arbitrary data
        self.window.show_input_panel("Diff parameters?", self.last_diff, self.do_diff, None, None)
        self.window.last_diff = self

    def do_diff(self, diff_args):
        self.last_diff = diff_args
        if diff_args == '':
            diff_args = 'HEAD'
        print("Diff args: %s" % diff_args)

        parser = DiffParser(diff_args)

        # For now, just print some info...
        for f in parser.changed_files:
            print("File {} has changed".format(f.filename))
            f.parse_diff()
            for hunk in f.hunks:
                print(hunk.hunk_match.group(0))
                hunk.parse_diff()

class DiffFilesList(sublime_plugin.WindowCommand):
    def run(self):
        if self.window.last_diff:
            print("Using existing diff...")

class DiffParser(object):
    STAT_CHANGED_FILE = re.compile('\s*([\w\.\-]+)\s*\|')

    def __init__(self, diff_args):
        self.diff_args = diff_args
        self.changed_files = self._get_changed_files()

    def _get_changed_files(self):
        files = []
        for line in git_command(['diff', '--stat', self.diff_args]).split('\n'):
            match = self.STAT_CHANGED_FILE.match(line)
            if match:
                files.append(FileDiff(match.group(1), self.diff_args))
        return files

class FileDiff(object):
    HUNK_MATCH = re.compile('^@@ \-(\d+),(\d+) \+(\d+),(\d+) @@')

    def __init__(self, filename, diff_args):
        self.filename = filename
        self.diff_args = diff_args
        self.diff_text = ''
        self.hunks = []

    def parse_diff(self):
        if not self.diff_text:
            self.diff_text = git_command(['diff', self.diff_args, '--minimal', '--word-diff=porcelain', '--', self.filename])
            hunk = None
            for line in self.diff_text.split('\n'):
                match = self.HUNK_MATCH.match(line)
                if match:
                    hunk = HunkDiff(match)
                    self.hunks.append(hunk)
                elif hunk:
                    hunk.diff_text_lines.append(line)

class HunkDiff(object):
    LINE_DELIM_MATCH = re.compile('^~')
    ADD_LINE_MATCH = re.compile('^\+(.*)')
    DEL_LINE_MATCH = re.compile('^\-(.*)')

    def __init__(self, hunk_match):
        self.hunk_match = hunk_match
        self.diff_text_lines = []
        self.line_diffs = []

    def parse_diff(self):
        old_line_num = int(self.hunk_match.group(1)) - 1
        new_line_num = int(self.hunk_match.group(3)) - 1
        old_line = ''
        new_line = ''

        for line in self.diff_text_lines:
            delim_match = self.LINE_DELIM_MATCH.match(line)
            add_match = self.ADD_LINE_MATCH.match(line)
            del_match = self.DEL_LINE_MATCH.match(line)

            if delim_match:
                if old_line or new_line:
                    self.line_diffs.append(LineDiff(old_line_num, old_line, new_line_num, new_line))
                if not old_line and not new_line:
                    old_line_num += 1
                    new_line_num += 1
                old_line = ''
                new_line = ''
            elif add_match:
                new_line_num += 1
                new_line = add_match.group(1)
            elif del_match:
                old_line_num += 1
                old_line = del_match.group(1)

class LineDiff(object):
    def __init__(self, old_line_number, old_line, new_line_number, new_line):
        self.old_line_number = old_line_number
        self.old_line = old_line
        self.new_line_number = new_line_number
        self.new_line = new_line
        print("Creating LineDiff with:")
        print("  Old line ({}): {}".format(old_line_number, old_line))
        print("  New line ({}): {}".format(new_line_number, new_line))

def git_command(args):
    p = subprocess.Popen(['git'] + args,
                         stdout=subprocess.PIPE,
                         shell=True)
    out, err = p.communicate()
    return out.decode('utf-8')