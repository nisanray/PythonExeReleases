Icons folder for Material Symbols used by the app.

How to use

1. To download SVGs for the icon list, run the downloader script:

```powershell
python download_material_symbols.py
```

2. The script will attempt to fetch SVG assets from the Google `material-design-icons` GitHub repository and save them to this folder as `<icon_name>.svg`.

3. If some icons are missing, manually download them from https://fonts.google.com/icons by searching the icon name and choosing "SVG / Download".

Font alternative

- If you prefer not to bundle SVGs, you can use the Material Symbols font (via Google Fonts) and render glyphs directly in the UI.
- To embed the font for offline use, download the family from Google Fonts (visit https://fonts.google.com and search "Material Symbols") and add the font files to your application resources.

License

Icons and fonts come from Google; review the license on Google Fonts / the Material Icons project before redistribution.