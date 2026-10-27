# -*- coding: utf-8 -*-
"""
Microphone -> words, with the speech recognizer built into Windows
(System.Speech, English, works offline). It listens only for the words we
give it, which makes it much more reliable than free dictation.

A small PowerShell script does the listening and prints one line per event:
  READY                      microphone is open
  HEARD|<word>|<confidence>  a word from the list (confidence 0..1)
  ERROR|<message>            no microphone / no English recognizer / ...
"""

import base64
import subprocess
import threading


def speech_script(words, wav=None):
    """The PowerShell script. wav: listen to a .wav file instead of the microphone."""
    choices = ",".join("'%s'" % w for w in words)
    source = f"$rec.SetInputToWaveFile('{wav}')" if wav else "$rec.SetInputToDefaultAudioDevice()"
    from_file = "$true" if wav else "$false"
    return f"""
$ErrorActionPreference = 'Stop'
try {{
  Add-Type -AssemblyName System.Speech
  $culture = New-Object System.Globalization.CultureInfo('en-US')
  $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
  $choices = New-Object System.Speech.Recognition.Choices
  $choices.Add([string[]]@({choices}))
  $gb = New-Object System.Speech.Recognition.GrammarBuilder($choices)
  $gb.Culture = $culture
  $rec.LoadGrammar((New-Object System.Speech.Recognition.Grammar($gb)))
  {source}
  [Console]::WriteLine('READY')
  $inv = [System.Globalization.CultureInfo]::InvariantCulture
  $quiet = 0
  while ($true) {{
    $r = $rec.Recognize([TimeSpan]::FromSeconds(2))
    if ($r -ne $null) {{
      $quiet = 0
      [Console]::WriteLine('HEARD|' + $r.Text + '|' + $r.Confidence.ToString($inv))
    }} elseif ({from_file}) {{
      $quiet++
      if ($quiet -ge 2) {{ break }}
    }}
  }}
}} catch {{
  [Console]::WriteLine('ERROR|' + $_.Exception.Message)
}}
"""


def powershell_command(script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-EncodedCommand", encoded]


class VoiceListener:
    """Runs the script in the background. on_event(kind, text, confidence) is called
    from a worker thread with kind = ready / heard / error / ended."""

    def __init__(self, words, on_event):
        self.words = words
        self.on_event = on_event
        self.proc = None

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self):
        if self.running:
            return
        self.proc = subprocess.Popen(
            powershell_command(speech_script(self.words)),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc):
        for line in proc.stdout:
            line = line.strip()
            if line == "READY":
                self.on_event("ready", "", 0.0)
            elif line.startswith("HEARD|"):
                parts = line.split("|")
                try:
                    self.on_event("heard", parts[1], float(parts[2]))
                except (IndexError, ValueError):
                    pass
            elif line.startswith("ERROR|"):
                self.on_event("error", line[6:], 0.0)
        self.on_event("ended", "", 0.0)

    def stop(self):
        if self.proc:
            try:
                self.proc.kill()
            except Exception:
                pass
            self.proc = None
