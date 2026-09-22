# Documentation

Documentation should be updated with any major feature updates, or to correct the documentation if it is outdated or incorrect.

You are encouraged to write the documentation yourself, but you may use an agent if you wish.

Please keep the documentation readable - shorter, more user-friendly documentation is preferred over detailed documentation.

Do not write documentation for simple changes or bugfixes, unless it invalidates any existing documentation.

## Previewing Changes

Preview the documentation locally:

```sh
uv run mkdocs serve --strict
```

Any changes you make to the docs will automatically be reflected in the local server.

## Updating the Documentation Site

Any merge into the `main` branch will automatically rebuild and update the documentation site.
