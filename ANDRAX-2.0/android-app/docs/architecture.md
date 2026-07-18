# ANDRAX 2.0 — Android App Architecture

The app is a **thin front-end**. It renders the ANDRAX-style category/tool
browser and dispatches execution to the Termux backend. It never performs
privileged or kernel-level operations — those are impossible on stock Android
and unnecessary for this design.

## Layers

```
┌──────────────────────────────────────────────────────────┐
│ UI (Activities)                                            │
│   MainActivity → CategoryListActivity → ToolListActivity   │
│                                       → ToolDetailActivity  │
├──────────────────────────────────────────────────────────┤
│ Data                                                       │
│   ToolRepository  (parses assets/tool_registry.json)       │
│   model: Category, Tool                                     │
├──────────────────────────────────────────────────────────┤
│ Launcher bridge                                            │
│   TermuxLauncher  (RUN_COMMAND intent → engine.sh)         │
└──────────────────────────────────────────────────────────┘
             │  com.termux.RUN_COMMAND intent
             ▼
     Termux backend (scripting-engine/engine.sh)
```

## Data model & catalog

* `model/Category.kt`, `model/Tool.kt` mirror the registry JSON schema.
* `data/ToolRepository.kt` reads `assets/tool_registry.json` (a copy of
  `launcher-system/tool_registry.json`) with `org.json`, caches the result, and
  exposes `categories()`, `category(id)`, `tool(id)`.
* Because both the app and the backend read the same registry, tool ids and
  script paths never drift. Sync the asset whenever the backend registry
  changes (see `INSTALL.md`).

## Screens

| Screen                | Responsibility                                          |
|-----------------------|---------------------------------------------------------|
| `MainActivity`        | Entry point; forwards to the category browser.          |
| `CategoryListActivity`| Lists categories in a `RecyclerView`.                   |
| `ToolListActivity`    | Lists tools inside a chosen category.                   |
| `ToolDetailActivity`  | Shows a tool, takes arguments, and the **Run** button.  |

The prototype builds views programmatically to stay dependency-light. A
production build would use XML layouts or Jetpack Compose (see `build-notes.md`
for the Compose equivalent of `ToolDetailActivity`).

## The Termux bridge

`launcher/TermuxLauncher.kt` sends Termux's documented `RUN_COMMAND` intent to
`com.termux.app.RunCommandService`:

```
RUN_COMMAND_PATH      = …/ANDRAX-2.0/scripting-engine/engine.sh
RUN_COMMAND_ARGUMENTS = ["run-tool", "<id>", "--", "<arg>", …]
RUN_COMMAND_WORKDIR   = …/ANDRAX-2.0
RUN_COMMAND_BACKGROUND= false      # foreground session so the user sees output
```

This requires (one-time): Termux installed, `allow-external-apps=true` in
`~/.termux/termux.properties`, and the `com.termux.permission.RUN_COMMAND`
permission granted to this app. If Termux is missing, the launcher opens its
F-Droid page.

### Why intents, not a socket/HTTP server?

* No background service to keep alive, no extra attack surface.
* The user always sees a real terminal session with live output and can Ctrl-C.
* Works within Android's app-sandbox and background-execution limits.

An alternative bridge (documented, not default) is a local Unix socket that a
`termux-services` daemon listens on; the intent approach is simpler and needs no
always-on process.

## Security & input handling

* The prototype tokenizes the argument field naively (`split` on whitespace). A
  production build must use a shell-aware splitter and validate/escape arguments
  before handing them to Termux.
* The app declares only `INTERNET` (for the F-Droid fallback) and the Termux
  RUN_COMMAND permission — nothing else.
* Authorization acknowledgement is enforced by the backend (`require_scope`),
  not the app, so it applies to CLI use too.
