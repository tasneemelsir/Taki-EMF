"""
A small stand-in for cmd.exe, for testing install-desktop.bat where there is no Windows.

It understands only what that script uses: set, if (exist / defined / errorlevel /
string comparison, also chained), goto, call :label, exit /b, for over a list and
over a file pattern, mkdir, rmdir, del, move, echo, and running programs. Files live
in a pretend file system (a set of paths), and programs are whatever the test hands in.

It follows cmd.exe in the two things that most often break a batch file:

  * variables are put in BEFORE a line is read as a command, so a folder name with
    an ampersand or a bracket in it splits or closes the command unless it sits
    inside quotes;
  * a jump to a label that is not there stops the script.

It is not Windows. It checks the script's logic: which way it goes, and what it
would run, in each situation.
"""

from __future__ import annotations

import fnmatch
import re
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

LOOP = "\x00"          # stands for the %% of a for-variable while the rest of the line is expanded


def norm(path: str) -> str:
    """Paths compare the Windows way: no quotes, either slash, any case, no trailing slash."""
    p = path.strip().strip('"').replace("/", "\\").lower()
    while p.endswith("\\.") or (p.endswith("\\") and not p.endswith(":\\")):
        p = p[:-2] if p.endswith("\\.") else p[:-1]
    return p


def split_outside_quotes(text: str, sep: str) -> List[str]:
    parts, cur, quoted = [], "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        if ch == sep and not quoted:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return parts + [cur]


def words(text: str) -> List[str]:
    """Split a command into words; a quoted stretch is one word (its quotes kept, as cmd keeps them)."""
    out, cur, quoted = [], "", False
    for ch in text.strip():
        if ch == '"':
            quoted = not quoted
            cur += ch
        elif ch.isspace() and not quoted:
            if cur:
                out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + ([cur] if cur else [])


class BatchError(AssertionError):
    """The script did something cmd.exe would choke on."""


class Batch:
    def __init__(self, text: str, script: str, files: Set[str], env: Dict[str, str],
                 program: Callable[[List[str], "Batch"], int], argv: Sequence[str] = ()) -> None:
        self.lines = text.replace("\r\n", "\n").split("\n")
        self.labels = {ln[1:].strip().lower(): i for i, ln in enumerate(self.lines) if ln.startswith(":")}
        self.script = script                                   # full path of the .bat, as Windows would give it
        self.files = {norm(f) for f in files}
        self.env = {k.upper(): v for k, v in env.items()}
        self.program, self.argv = program, list(argv)
        self.errorlevel = 0
        self.ran: List[List[str]] = []                         # every program started, in order
        self.said: List[str] = []                              # every line shown
        self.steps = 0

    # ----------------------------------------------------------- the file system
    def exists(self, path: str) -> bool:
        p = norm(path)
        return p in self.files or any(f.startswith(p + "\\") for f in self.files)

    def add(self, path: str) -> None:
        self.files.add(norm(path))

    def remove_tree(self, path: str) -> None:
        p = norm(path)
        self.files = {f for f in self.files if f != p and not f.startswith(p + "\\")}

    # ------------------------------------------------------------------ expansion
    def expand(self, line: str, args: Sequence[str]) -> str:
        line = line.replace("%%", LOOP)
        line = line.replace("%~dp0", self.script[:self.script.rfind("\\") + 1])
        line = line.replace("%*", " ".join(self.argv))
        line = re.sub(r"%([1-9])", lambda m: args[int(m.group(1)) - 1] if int(m.group(1)) <= len(args) else "", line)

        def value(m: "re.Match[str]") -> str:
            text = self.env.get(m.group(1).upper(), "")
            if m.group(2):                                     # %NAME:~start,length%
                start, _, length = m.group(2)[2:].partition(",")
                text = text[int(start):]
                if length:
                    text = text[:int(length)] if int(length) >= 0 else text[:int(length)]
            return text
        return re.sub(r"%([A-Za-z_][A-Za-z0-9_()]*)(:~-?\d+(?:,-?\d+)?)?%", value, line)

    # ------------------------------------------------------------------- running
    def run(self, start: int = 0, args: Sequence[str] = ()) -> int:
        pc = start
        while pc < len(self.lines):
            self.steps += 1
            if self.steps > 5000:
                raise BatchError("the script goes round in circles")
            line = self.lines[pc]
            pc += 1
            action = self.execute(self.expand(line, args), args)
            if action is None:
                continue
            kind, what = action
            if kind == "exit":
                return int(what)
            if what not in self.labels:
                raise BatchError(f"goto {what}: there is no such label")
            pc = self.labels[what] + 1
        return self.errorlevel

    def execute(self, text: str, args: Sequence[str]) -> Optional[Tuple[str, object]]:
        text = text.strip().lstrip("@").strip()
        if not text or text.startswith(":") or re.match(r"rem(\s|$)", text, re.I):
            return None
        pieces = split_outside_quotes(text, "&")
        if len(pieces) > 1:
            # The script joins commands with & in one place only (endlocal & exit). Anywhere else an
            # ampersand outside quotes came out of a folder name, and cmd.exe would cut the line there.
            if not all(re.match(r"(endlocal|exit)\b", piece.strip(), re.I) for piece in pieces):
                raise BatchError(f"an ampersand outside quotes splits this line: {text}")
            for piece in pieces:
                action = self.execute(piece, args)
                if action:
                    return action
            return None
        low = text.lower()
        if low.startswith("if "):
            return self._if(text[3:].strip(), args)
        if low.startswith("for "):
            return self._for(text, args)
        # ">nul" and "2>nul" only hide what a command prints; nothing else is redirected in this script
        text = "".join(seg if i % 2 else re.sub(r"\s*\d?>\s*nul\b", "", seg, flags=re.I)
                       for i, seg in enumerate(re.split(r'("[^"]*")', text)))
        if re.search(r"[<>|]", "".join(re.split(r'"[^"]*"', text))):
            raise BatchError(f"a redirection or pipe this stand-in does not expect: {text}")
        w = words(text)
        cmd = w[0].lower()
        if cmd in ("setlocal", "endlocal", "title", "pause"):
            return None
        if cmd == "echo" or cmd.startswith("echo."):
            self.said.append(text[4:].strip())
            return None
        if cmd == "set":
            m = re.match(r'set\s+"([^=]+)=(.*)"\s*$', text, re.I)
            if not m:
                raise BatchError(f"set without quotes round it: {text}")
            if m.group(2):
                self.env[m.group(1).upper()] = m.group(2)
            else:
                self.env.pop(m.group(1).upper(), None)
            return None
        if cmd == "goto":
            return ("goto", w[1].lstrip(":").lower())
        if cmd == "call":
            label = w[1].lstrip(":").lower()
            if label not in self.labels:
                raise BatchError(f"call :{label}: there is no such label")
            self.errorlevel = self.run(self.labels[label] + 1, w[2:])
            return None
        if cmd == "exit":
            code = int(w[2]) if len(w) > 2 and w[2].lstrip("-").isdigit() else self.errorlevel
            self.errorlevel = code
            return ("exit", code)
        if cmd == "mkdir":
            self.add(w[1])
            return None
        if cmd == "rmdir":
            self.ran.append(w)
            if self.program(w, self) == 0:
                self.remove_tree(w[-1])
            return None
        if cmd == "del":
            self.files.discard(norm(w[-1]))
            return None
        if cmd == "move":
            src, dst = w[-2], w[-1]
            if norm(src) in self.files:
                self.files.discard(norm(src))
                self.add(dst)
            else:
                self.errorlevel = 1
            return None
        self.ran.append(w)                                     # anything else is a program
        self.errorlevel = self.program(w, self)
        return None

    def _if(self, rest: str, args: Sequence[str]) -> Optional[Tuple[str, object]]:
        negate = False
        if rest.lower().startswith("not "):
            negate, rest = True, rest[4:].strip()
        low = rest.lower()
        if low.startswith("exist "):
            m = re.match(r'exist\s+("[^"]*"|\S+)\s+(.*)$', rest, re.I)
            truth, command = self.exists(m.group(1)), m.group(2)
        elif low.startswith("defined "):
            m = re.match(r"defined\s+(\S+)\s+(.*)$", rest, re.I)
            truth, command = m.group(1).upper() in self.env, m.group(2)
        elif low.startswith("errorlevel "):
            m = re.match(r"errorlevel\s+(\d+)\s+(.*)$", rest, re.I)
            truth, command = self.errorlevel >= int(m.group(1)), m.group(2)
        else:
            m = re.match(r'(/i\s+)?("[^"]*")==("[^"]*")\s+(.*)$', rest, re.I)
            if not m:
                raise BatchError(f"an if this stand-in cannot read: {rest}")
            a, b = m.group(2), m.group(3)
            truth, command = (a.lower() == b.lower()) if m.group(1) else (a == b), m.group(4)
        return self.execute(command, args) if truth != negate else None

    def _for(self, text: str, args: Sequence[str]) -> Optional[Tuple[str, object]]:
        m = re.match(rf"for\s+{LOOP}(\w)\s+in\s+\(", text, re.I)
        if not m:
            raise BatchError(f"a for this stand-in cannot read: {text}")
        var, rest, depth_quoted, end = m.group(1), text[m.end():], False, -1
        for i, ch in enumerate(rest):                          # the closing bracket: the first one outside quotes
            if ch == '"':
                depth_quoted = not depth_quoted
            elif ch == ")" and not depth_quoted:
                end = i
                break
        body = re.match(r"\s*do\s+(.*)$", rest[end + 1:], re.I)
        if end < 0 or not body:
            raise BatchError(f"the brackets of this for do not close where they should: {text}")
        items: List[str] = []
        for item in words(rest[:end]):
            if "*" in item:                                    # a file pattern: the files that match it
                pattern = norm(item)
                folder = pattern[:pattern.rfind("\\")]
                items += sorted(f for f in self.files if f.startswith(folder + "\\") and "\\" not in f[len(folder) + 1:]
                                and fnmatch.fnmatchcase(f, pattern.replace("[", "[[]")))
            else:
                items.append(item)
        for item in items:
            line = body.group(1).replace(f"{LOOP}~f{var}", item.strip('"')).replace(f"{LOOP}{var}", item)
            action = self.execute(line, args)
            if action:
                return action
        return None
