# Fonts

The app ships its own faces, so every reader sees the same type as the deck,
the diagrams and the demo videos.

| File | Face | Used for | License |
| --- | --- | --- | --- |
| `Bitter-Variable.woff2` | Bitter, weights 100 to 900 | Page titles and section headings | SIL Open Font License 1.1 (`OFL-Bitter.txt`) |
| `Inter-Regular.woff2`, `Inter-Medium.woff2`, `Inter-SemiBold.woff2`, `Inter-Bold.woff2` | Inter | Body text and controls | SIL Open Font License 1.1 (`OFL-Inter.txt`) |

Each file is a Latin subset made with `pyftsubset` (fonttools) from the
upstream release, about 120 KB in all. The `@font-face` rules are at the
bottom of `static/css/app.css`. Figures in tables use the reader's own
monospace face.

Do not swap in a CDN link. The app has to build and run under a deny-by-default
egress policy, and a webfont request there is a missing font plus a failed
request in the network log, not a fallback. Self-hosted files load from the
app's own origin and need no egress.
