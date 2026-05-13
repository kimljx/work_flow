Place runtime-configurable files here.

- `task-import-template.xlsx`: if present, the task template download API returns this file directly.
- `runtime-settings.json`: created by the system when scheduler settings are saved from the admin page.
- Browser certificates used by Playwright login can be placed here, for example `.cer`, `.crt`, `.pem`, `.p12`, or `.pfx`.
- Offline packaging scripts copy supported files from this directory into the release package `config/` directory.
- If the target site requires client-certificate login, a public `.cer` file alone may not be enough; you may also need a matching private-key container such as `.p12` or `.pfx`, or import the CA certificate into the target system/browser trust store.
