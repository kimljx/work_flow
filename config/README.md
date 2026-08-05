Place runtime-configurable files here.

- `task-import-template.xlsx`: if present, the task template download API returns this file directly.
- `runtime-settings.json`: created by the system when scheduler settings are saved from the admin page.
- Offline packaging scripts copy supported files from this directory into the release package `config/` directory.
- QAX and other HTTPS certificates are imported at the system trust-store level. Do not place runtime certificate files in this directory for production deployment.
