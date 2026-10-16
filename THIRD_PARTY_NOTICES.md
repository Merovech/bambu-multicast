# Third-party notices

This project includes material from the following third-party source.

## ha-bambulab

`server/print_errors.json` is derived from the English error-text table in the
[ha-bambulab](https://github.com/greghesp/ha-bambulab) Home Assistant integration
(`custom_components/bambu_lab/pybambu/hms_error_text/hms_en.json.gz`, the `device_error` section).
Entries with blank text were removed, and where the source words an error differently per printer
model, the generic wording was kept.

The error messages themselves are Bambu Lab's text. ha-bambulab compiles and distributes them, and
its license does not extend to Bambu Lab's wording.

ha-bambulab is distributed under the following license:

```
MIT License

Copyright (c) 2023 ha-bambulab contributors

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
