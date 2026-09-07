# Third-Party Notices

## mlx-lm

StateBraid Phase 1 and Phase 1.5 were developed from experiments performed on a local thin fork of Apple's `mlx-lm`. The StateBraid core rewrites the reviewed compute-continuity policy behind a backend-neutral contract; it does not vendor the MLX-LM package or its cache trie implementation.

The optional MLX adapter and the exact-hit generation-safety behavior are derived from work performed against `mlx-lm`, which is distributed under the MIT License:

> MIT License
>
> Copyright © 2023 Apple Inc.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

StateBraid itself is distributed under the Apache License 2.0 in `LICENSE`. The Apple
notice above is retained separately because the optional MLX adapter, exact-hit
generation-safety work, and packaged reference integration were derived from work
performed against mlx-lm. StateBraid's Apache-2.0 license does not replace or erase
the upstream MIT copyright and permission notice.
