# License & Legal Notice

## Software license

ANDRAX 2.0 (the glue scripts, launcher, workflow engine, scripting engine, and
Android app skeleton in this archive) is released under the **MIT License**:

```
MIT License

Copyright (c) 2026 ANDRAX 2.0 contributors

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
```

The third-party tools ANDRAX 2.0 installs and wraps (nmap, sqlmap, hydra, nikto,
the Metasploit Framework, mitmproxy, binwalk, John the Ripper, etc.) are each
licensed by their respective authors. ANDRAX 2.0 does **not** redistribute them;
it installs them from their upstream package repositories at setup time.

## Authorized-use notice

The tools bundled and orchestrated by ANDRAX 2.0 are dual-use security tools.
They are intended for:

* Testing systems, networks, and applications **you own**.
* Engagements where you have **explicit, written authorization** (a signed
  scope-of-work / rules-of-engagement).
* Capture-the-Flag competitions, lab environments, and security education.

Using these tools against systems without authorization is illegal in most
jurisdictions (e.g. the U.S. Computer Fraud and Abuse Act, the U.K. Computer
Misuse Act, and equivalents worldwide). **You** are solely responsible for how
you use ANDRAX 2.0. The authors accept no liability for misuse.

The launcher records an authorization acknowledgement on first run
(`~/.andrax/.authorized`). Do not bypass it for engagements you cannot document.
