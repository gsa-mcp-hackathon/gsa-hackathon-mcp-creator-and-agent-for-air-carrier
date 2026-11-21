# Fonts

Empty on purpose.

The app names Anthropic's faces first (`Styrene B`, `Styrene A`, `Tiempos
Text`) and falls back to the closest system equivalents. Those faces are
licensed and are not redistributable, so they are not in this repository.

If the organisation licenses them, put the woff2 files here and uncomment the
`@font-face` block at the bottom of `static/css/app.css`. Nothing else
changes.

Do not swap in a CDN link. The app has to build and run under a deny-by-default
egress policy, and a webfont request there is a missing font plus a failed
request in the network log, not a fallback.
