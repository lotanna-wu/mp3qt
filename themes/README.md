# Qt Themes

These themes are for the `qt-src` app and use a new schema.

## Layout

- `meta`: `name`, `version`, `author`
- `palette`: colors for controls and status states
- `typography`: fonts/sizes
- `metrics`: spacing, dimensions, border/radius
- `effects`: `field_shadow` and `status_shadow` (`plain|raised|sunken`)
- `images.window_bg`: optional background image path
- `qss`: optional custom Qt stylesheet additions

## Background image example

`images.window_bg` can be absolute or relative to the theme file:

```json
"images": {
  "window_bg": "../assets/wallpaper.png"
}
```

If the image path is invalid, the app falls back to a solid background color.
